using_tkinter = True

import xml.parsers.expat
from shapely.geometry import Polygon
if using_tkinter:
	from Tkinter import *


'''
Net should not know anything about polygons
'''
class Net:
	UNKNOWN = 0
	# V+
	VDD = 1
	VCC = 1
	# V-
	VSS = 2
	GND = 2
	# Pullup
	PU = 3
	# pulldown (unused)
	PD = 4
	
	def __init__(self, number=None):
		#self.polygons = set()
		# User definable set of objects in the net
		self.members = set()
		
		self.number = number
		self.potential = Net.UNKNOWN
		# Nets can have multiple names
		self.names = set()
		
	def add_member(self, member):
		self.members.add(member)
	
	def remove_member(self, member):
		self.members.remove(member)
		
	def add_name(self, name):
		self.names.add(name)
		
	def merge(self, other):
		for member in other.members:
			self.members.add(member)
		# Give us a net number if possible
		if self.number is None:
			self.number = other.number
		'''
		Any conflicting net status?
		Conflict
			VCC and GND
		Warning?
			PU/PD and VSS/GND
		Transition
			UNKNOWN and X: X
		'''
		# Expect most common case
		print 'net merge, potential = (self: %u, other: %u)' %(self.potential, other.potential)
		if self.potential == Net.UNKNOWN:
			self.potential = other.potential
		else:
			p1 = self.potential
			p2 = other.potential
			# Sort to reduce cases (want p1 lower)
			if p1 > p2:
				p = p1
				p1 = p2
				p2 = p
			# Expect most common case: both unknown
			if p2 == Net.UNKNOWN:
				pass
			# One known but not the other?
			elif p1 == Net.UNKNOWN:
				self.potential = p2
			elif p1 == Net.VDD and t2 == Net.GND:
				raise Exception("Supply shorted")
			elif (p1 == Net.VDD or p1 == Net.GND) and (p2 == Net.PU or p2 == Net.PD):
				print 'WARNING: eliminating pullup/pulldown status due to direct supply connection'
				self.potential = p1
			else:
				print p1
				print p2
				raise Exception('Unaccounted for net potential merge')
		print 'End potential: %u' % self.potential
		
	def pull_up(self):
		if self.potential == Net.UNKNOWN:
			self.potential = Net.PU
		# If alreayd at VCC pullup does nothing
		elif self.potential == Net.VDD:
			print 'WARNING: discarding pullup since at VDD'
			return
		elif self.potential == Net.GND:
			print 'WARNING: discarding pullup since at ground'
			return
		elif self.potential == Net.PD:
			raise Exception('Should not pull up and down')
		else:
			raise Exception('Unknown potential')
	
	def get_pullup(self):
		if self.potential == Net.PU:
			return '+'
		elif self.potential == Net.PD:
			raise Exception("not supported")
		else:
			return '-'
	
# Used in merging?
# decided to use map instead
'''
class NetProxy:
	def __init__(self, net):
		self.net = net
'''

class Nets:
	def __init__(self):
		# number to net object
		self.nets = dict()

	def __getitem__(self, net_number):
		return self.nets[net_number]

	def add(self, net):
		'''
		if not net.number in self.nets:
			s = set()
		else:
			s = self.nets[net.number]
		s.add(net)
		self.nets[net.number] = s
		'''
		self.nets[net.number] = net

	def merge(self, new_net, old_net):
		'''Move data from old_net number into new_net number'''
		self.nets[new_net].merge(self.nets[old_net])
		del self.nets[old_net]
				
class Point:
	def __init__(self, x, y):			
		self.x = x
		self.y = y

'''
Head up: may need to be able to do transforms if the canvas is relaly large
which shouldn't be too uncommon
'''
class PolygonRenderer:
	def __init__(self, title=None):
		# In render order
		# (polygon, color)
		self.targets = list()
		# Polygon color overrides
		# [polygon] = color
		# Make this usually not take up memory but can if you really want it
		self.colors = dict()
		self.title = title
		if self.title is None:
			self.title = 'Polygon render'

	# Specify color to override default or None for current
	def add_polygon(self, polygon, color=None):
		if color:
			self.colors[polygon] = color
		self.targets.append(polygon)
		
	def add_layer(self, layer, color=None):
		for polygon in layer.polygons:
			self.add_polygon(polygon, color)

	def add_xlayer(self, color=None):
		for polygon in layer.xpolygons:
			self.add_polygon(polygon, color)
		
	# Call after setup
	def render(self):
		if not using_tkinter:
			raise Exception("require tkinter")
			
		root = Tk()

		root.title(self.title)
		canvas = Canvas(root, width =400, height=400)

		# Upper left origin origin just like us
		#points = [1,1,10,1,10,10,1,10]
		for polygon in self.targets:
			points = list()
			
			# Use override if given
			if polygon in self.colors:
				color = self.colors[polygon]
			else:
				color = polygon.color
			if color is None:
				# Default to black
				color = 'black'
				
			for point in polygon.points:
				#print dir(point)
				points.append(point.x)
				points.append(point.y)
			canvas.create_polygon(points, fill=color)

		canvas.pack()
		#root.title(self.title)
		root.mainloop()

'''
Polygons are aware of anything need to draw them as well as their electrical properties
They are not currently aware of their material (layer) but probably need to be aware of it to figure out color
Currently color is pushed on instead of pulled
Final JSSim figures out color from layer and segdefs are pushed out on a layer by layer basis so its not necessary to store
'''
class UVPolygon:
	def __init__(self, points, color=None):
		'''
		To make display nicer
		Vaguely defined...HTML like
		Can either be a human color like red or green or HTML like #602030
		Consider making this external to a map so that we can compress a usually identical layer
		WARNING: this is for debugging and has nothing to do with render color in JSSim
		'''
		self.color = color
		# Number not the object
		self.net = None
		
		if points:
			self.set_polygon(Polygon([(point.x, point.y) for point in points]))
	
	def set_polygon(self, polygon):
		self.polygon = polygon
		self.rebuild_points()
		self.rebuild_xpolygon()
		#self.show("show self")
	
	def coordinates(self):
		'''return (JSSim style) single dimensional array of coordinates (WARNING: UL coordinate system)'''
		# return [i for i in [point.x,point.y) for point in self.points]
		# l = [(1, 2), (3, 4), (50, 32)]
		# print [i for i in [(x[0],x[1]) for x in l]]
		ret = list()
		for point in self.points:
			ret.append(point.x)
			ret.append(point.y)
		return ret
		
	@staticmethod
	def from_polygon(polygon):
		poly = UVPolygon(None)
		poly.polygon = polygon
		poly.net = None
		poly.rebuild_points()
		poly.rebuild_xpolygon()
		return poly
	
	def rebuild_points(self):
		self.points = list()
		for i in range(len(self.polygon.exterior.coords.xy[0]) - 1):
			x = self.polygon.exterior.coords.xy[0][i]
			y = self.polygon.exterior.coords.xy[1][i]
			#self.points.append((x, y))
			self.points.append(Point(x, y))
	
	def __repr__(self):
		ret = "<polygon points=\""
		first = True
		for point in self.points:
			# Space pairs to make it a little more readable
			if not first:
				ret += ', '
			ret += "%u,%u" % (point.x, point.y)
			first = False
		ret += '" />'
		return ret
		
	def union(self, other):
		poly = self.polygon.union(other.polygon)
		return UVPolygon.from_polygon(poly)

	def rebuild_xpolygon(self):
		'''
		Rebuild extended polygon
		Trys to find neighboring polygons by stretching about the centroid
		which we will then try to overlap
		'''
		
		centroid = self.polygon.centroid
		
		xbounds = list()
		increase = 2.0
		#print self.polygon.bounds
		# start and end are the same
		# Tech it will work though: optional in constructor
		for i in range(len(self.polygon.exterior.coords.xy[0]) - 1):
			#print i
			#print self.polygon.exterior.coords.xy
			x = self.polygon.exterior.coords.xy[0][i]
			y = self.polygon.exterior.coords.xy[1][i]
		
			#print x
			#print y
		
			if x - centroid.x < 0:
				x -= increase
			if x - centroid.x > 0:
				x += increase
			if y - centroid.y < 0:
				y -= increase
			if y - centroid.y > 0:
				y += increase
			xbounds.append((x, y))
		
		#print xbounds
		self.xpolygon = Polygon(xbounds)

	def intersects(self, polygon):
		# Check x intersect and y intersect
		# XXX: 
		return self.polygon.intersects(polygon.polygon)

	def intersection(self, polygon):
		intersected = self.polygon.intersection(polygon.polygon)
		if intersected.is_empty:
			return None
		return UVPolygon.from_polygon(intersected)

	@staticmethod
	def show_polygons(polygons):
		r = PolygonRenderer(title='Polygons')
		colors = ['red', 'blue', 'green', 'yellow']
		for i in range(0, len(polygons)):
			r.add_polygon(polygons[i], colors[i % len(colors)])
		r.render()
		
	def show(self, title='Polygon'):
		'''
		r = PolygonRenderer()
		points = list()
		for point in self.points:
			points.append(point.x)
			points.append(point.y)
		r.add_polygon(points, 'white')
		r.render()
		'''
		
		if not using_tkinter:
			raise Exception("require tkinter")

		root = Tk()

		root.title(title)
		canvas = Canvas(root, width =400, height=400)

		# Upper left origin origin just like us
		#points = [1,1,10,1,10,10,1,10]
		points = list()
		for point in self.points:
			points.append(point.x)
			points.append(point.y)
		canvas.create_polygon(points, fill='white')

		canvas.pack()
		root.mainloop()

	def points(self):
		ret = list()
		for i in range(len(self.polygon.exterior.coords.xy[0]) - 1):
			x = self.polygon.exterior.coords.xy[0][i]
			y = self.polygon.exterior.coords.xy[1][i]
			ret.append((x, y))
		return ret

# Intersected polygon
class UVPolygonI(UVPolygon):
	def __init__(self, points, poly1, poly2, color=None):
		UVPolygon.__init__(self, points, color)
		self.poly1 = poly1
		self.poly2 = poly2

# Layer intersection
# Intersection is arbitrary
# We may extend the actual layer polygon
# Don't make assumptions about how it relates to actual layers
class LayerI:
	def __init__(self, layer1, layer2, polygons):
		self.layer1 = layer1
		self.layer2 = layer2
		self.polygons = polygons

	def show(self, title=None):
		#UVPolygon.show_polygons(xintersections)
		r = PolygonRenderer(title)
		r.add_layer(self.layer1, 'red')
		r.add_layer(self.layer2, 'green')
		# Render intersection last
		for polygon in self.polygons:
			r.add_polygon(polygon, 'blue')
		r.render()

	# So can be further intersected
	def to_layer(self):
		layer = Layer()
		layer.polygons = self.polygons
		layer.name = 'Intersection of %s and %s' % (self.layer1.name, self.layer2.name)
		# Why not
		layer.color = 'blue'
		return layer

class LayerSVGParser:
	@staticmethod
	def parse(layer, file_name):
		parser = LayerSVGParser()
		parser.layer = layer
		parser.file_name = file_name
		parser.do_parse()

	def process_transform(self, transform):
		x_delta = float(transform.split(',')[0].split('(')[1])
		y_delta = float(transform.split(',')[1].split(')')[0])
		self.x_deltas.append(x_delta)
		self.y_deltas.append(y_delta)

		self.x_delta += x_delta
		self.y_delta += y_delta
		
	def pop_transform(self):
		self.x_delta -= self.x_deltas.pop()
		self.y_delta -= self.y_deltas.pop()
		
	def do_parse(self):
		'''
		Need to figure out a better parse algorithm...messy
		'''
		
		'''
		<rect
		   y="261.16562"
		   x="132.7981"
		   height="122.4502"
		   width="27.594412"
		   id="rect3225"
		   style="fill:#999999" />
		'''
		print self.file_name
		raw = open(self.file_name).read()
		
		print 'set vars'
		self.x_delta = 0.0
		self.x_deltas = list()
		self.y_delta = 0.0
		self.y_deltas = list()
		self.flow_root = False
		self.text = None

		# 3 handler functions
		def start_element(name, attrs):
			print 'Start element:', name, attrs
			if name == 'rect':				
				#print 'Got one!'
				# Origin at upper left hand corner, same as PIL
				# Note that inkscape displays origin as lower left hand corner...weird
				# style="fill:#00ff00"
				color = None
				if 'style' in attrs:
					style = attrs['style']
					color = style.split(':')[1]
				#if self.flow_root and self.text is None:
				#	raise Exception('Missing text')
				self.last_polygon = self.layer.add_rect(float(attrs['x']) + self.x_delta, float(attrs['y']) + self.y_delta, float(attrs['width']), float(attrs['height']), color=color)
			elif name == 'g':
				#transform="translate(0,-652.36218)"
				if 'transform' in attrs:
					transform = attrs['transform']
					self.process_transform(transform)
					self.g_transform = True
				else:
					self.g_transform = False
			elif name == 'svg':
			   self.layer.width = int(attrs['width'])
			   self.layer.height = int(attrs['height'])
			   print 'Width ' + str(self.layer.width)
			   print 'Height ' + str(self.layer.height)
			# Text entry
			elif name == 'flowRoot':
				'''
				<flowRoot
					transform="translate(15.941599,-0.58989212)"
					xml:space="preserve"
					id="flowRoot4100"
					style="font-size:12px;font-style:normal;font-variant:normal;font-weight:normal;font-stretch:normal;text-align:start;line-height:125%;writing-mode:lr-tb;text-anchor:start;fill:#000000;fill-opacity:1;stroke:none;display:inline;font-family:Bitstream Vera Sans;-inkscape-font-specification:Bitstream Vera Sans">
					<flowRegion id="flowRegion4102">
						<rect
							id="rect4104"
							width="67.261375"
							height="14.659531"
							x="56.913475"
							y="189.59261"
							style="fill:#000000" />
					</flowRegion>
					<flowPara id="flowPara4106">
						clk0
					</flowPara>
				</flowRoot>
				'''
				self.flow_root = True
				self.text = None
				
				if 'transform' in attrs:
					transform = attrs['transform']
					self.flowRoot_transform = True
					self.process_transform(transform)
				else:
					self.flowRoot_transform = False
					
			elif name == 'flowPara':
				#self.text = attrs
				#print 'TEXT: ' + repr(self.text)
				#sys.exit(1)
		   		pass
		   	else:
		   		print 'Skipping %s' % name
				pass
		   
			
		def end_element(name):
			#print 'End element:', name
			
			if name == 'flowRoot':
				self.last_polygon.text = self.text

				self.flow_root = False
				self.text = None
				self.last_polygon = None
				if self.flowRoot_transform:
					self.pop_transform()
					self.flowRoot_transform = False
			elif name == 'g':
				if self.g_transform:
					self.pop_transform()
					self.g_transform = False
			pass
		def char_data(data):
			#print 'Character data:', repr(data)
			self.text = data
			pass

	 	p = xml.parsers.expat.ParserCreate()

		p.StartElementHandler = start_element
		p.EndElementHandler = end_element
		p.CharacterDataHandler = char_data

		p.Parse(raw, 1)


# (Mask) layer
# In practice for now this is simply an SVG image
class Layer:
	METAL = 0
	DIFFUSION = 1
	PROTECTION = 2
	GROUNDED_DIFFUSION = 3
	POWERED_DIFFUSION = 4
	POLYSILICON = 5

	# unknown metal just in case
	UNKNOWN_METAL = 100
	# we figure this out, net given
	UNKNOWN_DIFFUSION = 101
	
	def __init__(self):
		self.index = None
		#self.pimage = PImage(image_file_name)
		self.polygons = set()
		self.name = None
		# Default color if polygon doesn't have one
		self.color = None
		self.potential = Net.UNKNOWN
		#self.virtual = False

	@staticmethod
	def is_valid(layer_index):
		return layer_index >= 0 and layer_index <= 5

	@staticmethod
	def from_layers(layers, name=None):
		ret = Layer()
		#ret.virtual = True
		for layer in layers:
			for polygon in layer.polygons:
				ret.polygons.add(polygon)
		ret.name = name
		return ret
	
	def show(self, title=None):
		r = PolygonRenderer(title)
		r.add_layer(self)
		r.render()

	def gen_polygons(self):
		for polygon in self.polygons:
			yield polygon
		
	def remove_polygon(self, polygon):
	
		print self.polygons
		self.polygons.remove(polygon)
		
	def assign_nets(self, netgen):
		for polygon in self.polygons:
			if polygon.net is None:
				polygon.net = netgen.get_net()
				# This polygon is the only member in the net so far
				polygon.net.add_member(polygon)
				# If the layer has a potential defined to it, propagate it
				polygon.net.potential = self.potential
				print 'self potential: %u' % self.potential

	def __repr__(self):
		ret = 'Layer: '
		sep = ''
		for polygon in self.polygons:
			ret += polygon.__repr__() + sep
			sep = ', '
		return ret
		
	def get_name(self):
		return self.name

	def intersection(self, other, do_xintersection=True):
		# list of intersecting polygons
		xintersections = list()
		print 'Checking intersection of %s (%u) and %s (%u)' % (self.name, len(self.polygons), other.name, len(other.polygons))
		
		def gen_pairs_normal():
			'''Normal polygon generator where polygons don't repeat'''
			for self_polygon in self.polygons:
				for other_polygon in other.polygons:
					yield (self_polygon, other_polygon)
		
		def gen_pairs_same():
			'''Avoid comparing against self'''
			tried = set()
			polygons = list(self.polygons)
			# Trim off i = 0 case (range(0, 0) = [])
			for i in range(1, len(polygons)):
				for j in range(0, i):
					yield (polygons[i], polygons[j])
					
		if self == other:
			polygen = gen_pairs_same()
		else:
			polygen = gen_pairs_normal()
		
		for (self_polygon, other_polygon) in polygen:
			if do_xintersection:
				poly1 = self_polygon.xpolygon
				poly2 = other_polygon.xpolygon
			else:
				poly1 = self_polygon.polygon
				poly2 = other_polygon.polygon
			
			if False:
				print 'Checking:'
				print '\t%s: %s' % (self.name, poly1)
				print '\t%s: %s' % (other.name, poly2)
			
			if poly1.intersects(poly2):
				print 'Intersection!'
				print '%s %s vs %s %s' % (self.name, poly1, other.name, poly2)
				xintersection = UVPolygon.from_polygon(poly1).intersection(UVPolygon.from_polygon(poly2))
				# Tack on some intersection data
				xintersection.poly1 = self_polygon
				xintersection.poly2 = other_polygon
				xintersections.append(xintersection)
		return LayerI(self, other, xintersections)

	@staticmethod
	def from_svg(file_name):
		p = Layer()
		p.do_from_svg(file_name)
		p.name = file_name
		return p
				
	def do_from_svg(self, file_name):
		LayerSVGParser.parse(self, file_name)
	
	def add_rect(self, x, y, width, height, color=None):
		return self.add_polygon(list([Point(x, y), Point(x + width, y), Point(x + width, y + height), Point(x, y + height)]), color=color)
		
	def add_polygon(self, points, color=None):
		polygon = UVPolygon(points, color=color)
		self.polygons.add(polygon)
		return polygon
		
	@staticmethod
	def show_layers(layers):
		r = PolygonRenderer(title='Layers')
		colors = ['red', 'blue', 'green', 'yellow']
		print 'item: ' + repr(layers.__class__)
		for i in range(0, len(layers)):
			r.add_layer(layers[i], colors[i % len(colors)])
		r.render()
