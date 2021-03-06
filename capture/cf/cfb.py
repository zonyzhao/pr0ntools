from PIL import Image, ImageDraw, ImageStat

states = 'vmu'
bitmap2fill = {
        'v':'white',
        'm':'blue',
        'u':'orange',
        }
bitmap2fill2 = {
        'v': (255, 255, 255, 255),
        'm': (0, 0, 255, 255),
        'u': (255, 165, 0, 255),
        }
fill2bitmap = {
        (255, 255, 255):'v',    # white
        (0, 0, 255):    'm',    # blue
        (255, 165, 0):  'u',    # orange
        }

# confocal bitmap
class CFB:
    def __init__(self):
        # 0: cols, 1: rows
        self.crs = [None, None]
        # linear grid equations on the original image
        self.xy_mb = [None, None]
        self.bitmap = None

    def cr(self, adj=0):
        for c in xrange(self.crs[0] + adj):
            for r in xrange(self.crs[1] + adj):
                yield (c, r)

    def xy(self, adj=0):
        '''Generate (x0, y0) upper left and (x1, y1) lower right (inclusive) tile coordinates'''
        for c in xrange(self.crs[0] + adj):
            (xm, xb) = self.xy_mb[0]
            x = int(xm * c + xb)
            for r in xrange(self.crs[1] + adj):
                (ym, yb) = self.xy_mb[1]
                y = int(ym * r + yb)
                yield (x, y), (x + xm, y + ym)

    def xy_cr(self, b=True, adj=0, sf=1.0):
        for c in xrange(self.crs[0] + adj):
            (xm, xb) = self.xy_mb[0]
            if not b:
                xb = 0.0
            x = int(xm * c + xb)
            for r in xrange(self.crs[1] + adj):
                (ym, yb) = self.xy_mb[1]
                if not b:
                    yb = 0.0
                y = int(ym * r + yb)
                yield ((int(x * sf), int(y * sf)), (int(int(x + xm) * sf), int(int(y + ym) * sf))), (c, r)

    def xy2cr(self, x, y, sf = 1.0):
        x = x / sf
        y = y / sf
        
        m, b = self.xy_mb[0]
        c = int((x - b) / m)

        m, b = self.xy_mb[1]
        r = int((y - b) / m)
        
        if c > self.crs[0]:
            raise ValueError("max col %d, got %d => %d" % (self.crs[0], x, c))
        if r > self.crs[1]:
            raise ValueError("max row %d, got %d => %d" % (self.crs[1], y, r))
        
        return (c, r)
    

# Save in enlarged form
# Colors are made to be easy to see
# and may contain annotations
# Not intended to be read back
def cfb_save_debug(cfb, fn):
    #im = self.preproc_im.copy()
    im = Image.new("RGB", (int(cfb.crs[0] * cfb.xy_mb[0][0]), int(cfb.crs[1] * cfb.xy_mb[1][0])), "white")
    draw = ImageDraw.Draw(im)
    for ((x0, y0), (x1, y1)), (c, r) in cfb.xy_cr(False):
        draw.rectangle((x0, y0, x1, y1), fill=bitmap2fill[cfb.bitmap[(c, r)]])
    im.save(fn)

# Save in minimal interchange format with one pixel per lambda
def cfb_save(cfb, fn):
    im = Image.new("RGB", cfb.crs, "white")
    draw = ImageDraw.Draw(im)
    for (c, r) in cfb.cr():
        draw.rectangle((c, r, c, r), fill=bitmap2fill[cfb.bitmap[(c, r)]])
    im.save(fn)

def cfb_verify(cfb):
    for (c, r) in cfb.bitmap:
        if c >= cfb.crs[0] or r >= cfb.crs[1]:
            raise Exception("Got c=%d, r=%d w/ global cs=%d, rs=%d" % (c, r, cfb.crs[0], cfb.crs[1]))

def filt_unk_lone(bitmap, unk_open):
    for c, r in set(unk_open):
        # look for adjacent
        if     (bitmap.get((c - 1, r), 'v') == 'v' and bitmap.get((c + 1, r), 'v') == 'v' and
                bitmap.get((c, r - 1), 'v') == 'v' and bitmap.get((c, r + 1), 'v') == 'v'):
            print '  Unknown %dc, %dr rm: lone' % (c, r)
            bitmap[(c, r)] = 'v'
            unk_open.discard((c, r))

def bitmap_netstat(bitmap, c, r, keep=lambda x: x in 'mu'):
    '''
    return dictionary with m and u keys
    each key holds a set with the cols and rows contiguous with start point c, r (including c, r)
    
    This could potentially blow through the stack for large polygons
    If problems optimize
    
    TODO: abort when find certain metal threshold?
    '''
    
    ret = {'m': set(), 'u': set()}
    checked = set()
    
    def check(c, r):
        #print 'check(%d, %d)' % (c, r)
        if (c, r) in checked:
            return
        this = bitmap.get((c, r), None)
        # Out of bounds?
        if this is None:
            return
        checked.add((c, r))
        # Void?  We are off the polygon: stop looking
        if not keep(this):
            return
        
        # got something
        ret[this].add((c, r))
        
        check(c - 1, r)
        check(c + 1, r)
        check(c, r - 1)
        check(c, r + 1)
    
    check(c, r)
    return ret

def trans_group(bitmap, c, r, to):
    '''Convert all same type tiles at c, r into to'''
    this = bitmap[(c, r)]
    bins = bitmap_netstat(bitmap, c, r, keep=lambda x: x in this)
    for (cm, rm) in bins[this]:
        bitmap[(cm, rm)] = to

'''
Remove any segments that are composed of only unknown and 0-1 positive matches
'''
def filt_unk_groups(cfb, unk_open):
    to_remove = set()
    checked = set()
    for c, r in set(unk_open):
        if (c, r) in checked:
            continue
        
        bins = bitmap_netstat(cfb.bitmap, c, r)
        checked = checked.union(bins['u'])
        
        def has_border_m():
            if len(bins['m']) == 0:
                return False
            for (cm, rm) in bins['m']:
                if      cm <= 2 or cm >= cfb.crs[0] - 2 or \
                        rm <= 2 or rm >= cfb.crs[1] - 2:
                    return True
            return False
        
        if len(bins['m']) <= 1:
            # if there's metal at a border keep it
            # tries to level out penalties for not being able to linearize these
            # keeping as warnings instead of removing
            # xxx: should just keep the unknown near the border?
            if has_border_m():
                continue
            print '  Unknown %dc, %dr rm: %d unknowns, %d metal' % (c, r, len(bins['u']), len(bins['m']))
            to_remove = to_remove.union(bins['u'])
            to_remove = to_remove.union(bins['m'])
    
    for cr in to_remove:
        cfb.bitmap[cr] = 'v'
        unk_open.discard(cr)

def prop_ag(cfb, bitmap_ag, unk_open):
    to_promote = set()
    for c, r in cfb.cr():
        # Skip if nothing is there
        if bitmap_ag[(c, r)] == 'v':
            continue
        # Do we already think something is there?
        if cfb.bitmap[(c, r)] == 'm':
            continue
        # Is there something to extend?
        if not has_around(cfb.bitmap, c, r, 'm', order=2):
            continue
        print '  %dc, %dr => m: join m' % (c, r)
        to_promote.add((c, r))
    for (c, r) in to_promote:
        cfb.bitmap[(c, r)] = 'm'
        unk_open.discard((c, r))

'''
def has_around(bitmap, c, r, t, d='v', order=1):
    return (bitmap.get((c - 1,  r),     d) != t and
            bitmap.get((c + 1,  r),     d) != t and
            bitmap.get((c,      r - 1), d) != t and
            bitmap.get((c,      r + 1), d) != t)
'''
def has_around(bitmap, c, r, t, d='v', order=1):
    '''Return true if d exists for order tiles in at least one direction around c, r'''
    # the four directions
    for cr in [
            lambda i: (c - i,  r),
            lambda i: (c + i,  r),
            lambda i: (c,      r - i),
            lambda i: (c,      r + i),
            ]:
        def check():
            # order tiles this direction match?
            for i in xrange(order + 1):
                if bitmap.get(cr(i), d) != t:
                    return False
            return True
        # this direction has a match?
        if check():
            return True
    # No direction matched
    return False

'''
If a single unknown is on a contiguous strip of metal its likely a via has distorted it
Note: this will ocassionally cause garbage to incorrectly merge nets
'''
def munge_unk_cont(bitmap, unk_open):
    # Don't propagate
    # Make a list and apply it after the sweep
    to_promote = set()
    for c, r in set(unk_open):
        # Abort if any adjacent unknowns
        if has_around(bitmap, c, r, 'u', order=1):
            continue
        # Is there surrounding metal forming a line? (or solid)
        if not has_around(bitmap, c, r, 'm', order=2):
            continue
        print '  Unknown %dc, %dr => m: join m' % (c, r)
        to_promote.add((c, r))
    for (c, r) in to_promote:
        bitmap[(c, r)] = 'm'
        unk_open.discard((c, r))
