# -*- coding: utf-8 -*-
#-------------------------------------------------
#-- osm map importer
#--
#-- microelly 2016 v 0.3
#--
#-- GNU Lesser General Public License (LGPL)
#-------------------------------------------------

#http://api.openstreetmap.org/api/0.6/map?bbox=11.74182,50.16413,11.74586,50.16561
#http://api.openstreetmap.org/api/0.6/way/384013089
#http://api.openstreetmap.org/api/0.6/node/3873106739

from say import *

import time, json, os

import urllib2

import pivy 
from pivy import coin


import FreeCAD,FreeCADGui, Part
App=FreeCAD
Gui=FreeCADGui

import geodat.transversmercator
from  geodat.transversmercator import TransverseMercator

import inventortools

import xmltodict
from  xmltodict import parse


#------------------------------
#
# microelly 2016 ..
#
#------------------------------

import time

def getheight(b,l):
	''' get height of a single point'''
	# hard coded no height 
	# return 0.0
	anz=0
	while anz<4:
			source="https://maps.googleapis.com/maps/api/elevation/json?locations="+str(b)+','+str(l)
			response = urllib2.urlopen(source)
			ans=response.read()
			if ans.find("OVER_QUERY_LIMIT"):
				anz += 1
				time.sleep(5)
			else:
				anz=10
	s=json.loads(ans)
	res=s['results']
	for r in res:
		return round(r['elevation']*1000,2)


def get_heights(points):
	''' get heights for a list of points'''
	i=0
	size=len(points)
	while i<size:
		source="https://maps.googleapis.com/maps/api/elevation/json?locations="
		ii=0
		if i>0:
			time.sleep(1)
		while ii < 20 and i < size:
			p=points[i]
			ss= p[1]+','+p[2] + '|'
			source += ss
			i += 1
			ii += 1
		source += "60.0,10.0"
		response = urllib2.urlopen(source)
		ans=response.read()
		s=json.loads(ans)
		res=s['results']
		heights= {}
		for r in res:
			key="%0.7f" %(r['location']['lat']) + " " + "%0.7f" %(r['location']['lng'])
			heights[key]=r['elevation']
	return heights


def organize():
	highways=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_highways")
	landuse=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_landuse")
	buildings=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_building")
	pathes=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_pathes")

	for oj in App.activeDocument().Objects:
		if oj.Label.startswith('building'):
			buildings.addObject(oj)
			# oj.ViewObject.Visibility=False
		if oj.Label.startswith('highway') or oj.Label.startswith('way'):
			highways.addObject(oj)
			oj.ViewObject.Visibility=False
		if oj.Label.startswith('landuse'):
			landuse.addObject(oj)
			oj.ViewObject.Visibility=False
		if oj.Label.startswith('w_'):
			pathes.addObject(oj)
			oj.ViewObject.Visibility=False


def import_osm(b,l,bk,progressbar,status):
	import_osm2(b,l,bk,progressbar,status,False)

def import_osm2(b,l,bk,progressbar,status,elevation):

	dialog=False
	debug=False

	if progressbar:
			progressbar.setValue(0)

	if status:
		status.setText("get data from openstreetmap.org ...")
		FreeCADGui.updateGui()
	content=''

	bk=0.5*bk
	dn=FreeCAD.ConfigGet("UserAppData") + "/geodat/"
	fn=dn+str(b)+'-'+str(l)+'-'+str(bk)
	import os
	if not os.path.isdir(dn):
		print "create " + dn
		os.makedirs(dn)

	try:
		f=open(fn,"r")
		content=f.read()
#		print content
	except:
		lk=bk # 
		b1=b-bk/1113*10
		l1=l-lk/713*10
		b2=b+bk/1113*10
		l2=l+lk/713*10
		source='http://api.openstreetmap.org/api/0.6/map?bbox='+str(l1)+','+str(b1)+','+str(l2)+','+str(b2)
		print source
		try:
			response = urllib2.urlopen(source)
			first=True
			content=''
			f=open(fn,"w")
			l=0
			z=0
			ct=0
			for line in response:
				if status:
					if z>5000:
						status.setText("read data ..." + str(l)) 
						z=0
					FreeCADGui.updateGui()
					l+=1
					z+=1
				if first:
					first=False
				else:
					content += line
					f.write(line)
			f.close()
			if status:
				status.setText("FILE CLOSED ..." + str(l))
				FreeCADGui.updateGui()
			response.close()
		except:
			print "Fehler beim Lesen"
		if status:
			status.setText("got data from openstreetmap.org ...")
			FreeCADGui.updateGui()
		print "Beeenden - im zweiten versuch daten auswerten"
		return

	if elevation:
		baseheight=getheight(b,l)
	else:
		baseheight=0 

	print "-------Data---------"
	print content
	print "--------------------"

	if status:
		status.setText("parse data ...")
		FreeCADGui.updateGui()

	sd=parse(content)
	if debug: print(json.dumps(sd, indent=4))

	if status:
		status.setText("transform data ...")
		FreeCADGui.updateGui()

	bounds=sd['osm']['bounds']
	nodes=sd['osm']['node']
	ways=sd['osm']['way']
	relations=sd['osm']['relation']


	# center of the scene
	bounds=sd['osm']['bounds']
	minlat=float(bounds['@minlat'])
	minlon=float(bounds['@minlon'])
	maxlat=float(bounds['@maxlat'])
	maxlon=float(bounds['@maxlon'])

	tm=TransverseMercator()
	tm.lat=0.5*(minlat+maxlat)
	tm.lon=0.5*(minlon+maxlon)

	center=tm.fromGeographic(tm.lat,tm.lon)
	corner=tm.fromGeographic(minlat,minlon)
	size=[center[0]-corner[0],center[1]-corner[1]]

	# map all points to xy-plane
	points={}
	nodesbyid={}
	for n in nodes:
		nodesbyid[n['@id']]=n
		ll=tm.fromGeographic(float(n['@lat']),float(n['@lon']))
		points[str(n['@id'])]=FreeCAD.Vector(ll[0]-center[0],ll[1]-center[1],0.0)

	# hack to catch deutsche umlaute
	def beaustring(string):
		res=''
		for tk in zz:
			try:
				res += str(tk)
			except:
				
				if ord(tk)==223:
					res += 'ß'
				elif ord(tk)==246:
					res += 'ö'
				elif ord(tk)==196:
					res += 'Ä'
				elif ord(tk)==228:
					res += 'ä'
				elif ord(tk)==242:
					res += 'ü'
				else:
					print ["error sign",tk,ord(tk),string]
					res +="#"
		return res

	if status:
		status.setText("create visualizations  ...")
		FreeCADGui.updateGui()

	App.newDocument("OSM Map")
	say("Datei erzeugt")
	area=App.ActiveDocument.addObject("Part::Plane","area")
	obj = FreeCAD.ActiveDocument.ActiveObject
	say("grundflaeche erzeugt")
	try:
		viewprovider = obj.ViewObject
		root=viewprovider.RootNode
		myLight = coin.SoDirectionalLight()
		myLight.color.setValue(coin.SbColor(0,1,0))
		root.insertChild(myLight, 0)
		say("beleuchtung auf grundobjekt eingeschaltet")
	except:
		sayexc("Beleuchtung 272")

	cam='''#Inventor V2.1 ascii
	OrthographicCamera {
	  viewportMapping ADJUST_CAMERA
	  orientation 0 0 -1.0001  0.001
	  nearDistance 0
	  farDistance 10000000000
	  aspectRatio 100
	  focalDistance 1
	'''
	x=0
	y=0
	height=1000000
	height=200*bk*10000/0.6
	cam += '\nposition ' +str(x) + ' ' + str(y) + ' 999\n '
	cam += '\nheight ' + str(height) + '\n}\n\n'
	FreeCADGui.activeDocument().activeView().setCamera(cam)
	FreeCADGui.activeDocument().activeView().viewAxonometric()
	say("Kamera gesetzt")
	
	area.Length=size[0]*2
	area.Width=size[1]*2
	area.Placement=FreeCAD.Placement(FreeCAD.Vector(-size[0],-size[1],0.00),FreeCAD.Rotation(0.00,0.00,0.00,1.00))
	say("Area skaliert")
	wn=-1
	coways=len(ways)
	starttime=time.time()
	refresh=1000
	for w in ways:
#		print w
		wid=w['@id']
#		print wid
		
		building=False
		landuse=False
		highway=False
		wn += 1

		# nur teile testen 
		#if wn <2000: continue

		nowtime=time.time()
		if wn<>0: print "way ---- # " + str(wn) + "/" + str(coways) + " time per house: " +  str(round((nowtime-starttime)/wn,2))
		if progressbar:
			progressbar.setValue(int(0+100.0*wn/coways))

		if debug: print "w=", w
		if debug: print "tags ..."
		st=""
		nr=""
		h=0
		try:
			w['tag']
		except:
			print "no tags found."
			continue

		for t in w['tag']:
			if t.__class__.__name__ == 'OrderedDict':
				try:
					if debug: print t

					if str(t['@k'])=='building':
						building=True
						st='building'

					if str(t['@k'])=='landuse':
						landuse=True
						st=w['tag']['@k']
						nr=w['tag']['@v']

					if str(t['@k'])=='highway':
						highway=True
						st=t['@k']

					if str(t['@k'])=='name':
						zz=t['@v']
						nr=beaustring(zz)
					if str(t['@k'])=='ref':
						zz=t['@v']
						nr=beaustring(zz)+" /"

					if str(t['@k'])=='addr:street':
						zz=w['tag'][1]['@v']
						st=beaustring(zz)
					if str(t['@k'])=='addr:housenumber':
						nr=str(t['@v'])

					if str(t['@k'])=='building:levels':
						if h==0:
							h=int(str(t['@v']))*1000*3
					if str(t['@k'])=='building:height':
						h=int(str(t['@v']))*1000

				except:
					print "unexpected error ################################################################"

			else:
				if debug: print [w['tag']['@k'],w['tag']['@v']]
				if str(w['tag']['@k'])=='building':
					building=True
					st='building'
				if str(w['tag']['@k'])=='building:levels':
					if h==0:
						h=int(str(w['tag']['@v']))*1000*3
				if str(w['tag']['@k'])=='building:height':
					h=int(str(w['tag']['@v']))*1000

				if str(w['tag']['@k'])=='landuse':
					landuse=True
					st=w['tag']['@k']
					nr=w['tag']['@v']
				if str(w['tag']['@k'])=='highway':
					highway=True
					st=w['tag']['@k']
					nr=w['tag']['@v']

			name=str(st) + " " + str(nr)
			if name==' ':
				name='landuse xyz'
			if debug: print "name ",name

		#generate pointlist of the way
		polis=[]
		height=None
		
		llpoints=[]
		for n in w['nd']:
			m=nodesbyid[n['@ref']]
			llpoints.append([n['@ref'],m['@lat'],m['@lon']])
		if elevation:
			heights=get_heights(llpoints)

		for n in w['nd']:
			p=points[str(n['@ref'])]
			if building and elevation:
				if not height:
					try:
						height=heights[m['@lat']+' '+m['@lon']]*1000 - baseheight
					except:
						print "---no height avaiable for " + m['@lat']+' '+m['@lon']
						height=0
				p.z=height
			polis.append(p)

		#create 2D map
		pp=Part.makePolygon(polis)
		Part.show(pp)
		z=App.ActiveDocument.ActiveObject
		z.Label="w_"+wid

		if name==' ':
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			g.ViewObject.ShapeColor = (1.00,1.00,0.00)
			g.Dir = (0,0,10)
			g.Solid=True
			g.Label='way ex '

		if building:
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			g.ViewObject.ShapeColor = (1.00,1.00,1.00)

			if h==0:
				h=10000
			g.Dir = (0,0,h)
			g.Solid=True
			g.Label=name

			obj = FreeCAD.ActiveDocument.ActiveObject
			inventortools.setcolors2(obj)

		if landuse:
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			if nr == 'residential':
				g.ViewObject.ShapeColor = (1.00,.60,.60)
			elif nr == 'meadow':
				g.ViewObject.ShapeColor = (0.00,1.00,0.00)
			elif nr == 'farmland':
				g.ViewObject.ShapeColor = (.80,.80,.00)
			elif nr == 'forest':
				g.ViewObject.ShapeColor = (1.0,.40,.40)
			g.Dir = (0,0,0.1)
			g.Label=name
			g.Solid=True

		if highway:
			g=App.ActiveDocument.addObject("Part::Extrusion","highway")
			g.Base = z
			g.ViewObject.LineColor = (0.00,.00,1.00)
			g.ViewObject.LineWidth = 10
			g.Dir = (0,0,0.2)
			g.Label=name
		refresh += 1
		if os.path.exists("/tmp/stop"):
			
			print("notbremse gezogen")
			FreeCAD.w=w
			raise Exception("Notbremse Manager main loop")

		if refresh >3:
			FreeCADGui.updateGui()
			# FreeCADGui.SendMsgToActiveView("ViewFit")
			refresh=0


	FreeCAD.activeDocument().recompute()
	FreeCADGui.updateGui()
	FreeCAD.activeDocument().recompute()

	if status:
		status.setText("import finished.")
	if progressbar:
			progressbar.setValue(100)

	organize()

	endtime=time.time()
	print "running time ", int(endtime-starttime),  " count ways ", coways



import FreeCAD,FreeCADGui
import WebGui


#import geodat.import_osm
#reload(geodat.import_osm)

'''
{
   "error_message" : "You have exceeded your daily request quota for this API. We recommend registering for a key at the Google Developers Console: https://console.developers.google.com/",
   "results" : [],
   "status" : "OVER_QUERY_LIMIT"
}

'''


s6='''
#VerticalLayoutTab:
MainWindow:
#DockWidget:
	VerticalLayout:
		id:'main'
		setFixedHeight: 600
		setFixedWidth: 730
		setFixedWidth: 654
		move:  PySide.QtCore.QPoint(3000,100)

		QtGui.QLabel:
			setText:"C O N F I G U R A T I O N"
		QtGui.QLabel:
		QtGui.QLineEdit:
			setText:"50.340722, 11.232647"
#			setText:"50.3736049,11.191643"
#			setText:"50.3377879,11.2104096"
			id: 'bl'

		QtGui.QLabel:
		QtGui.QCheckBox:
			id: 'elevation' 
			setText: 'Process Elevation Data'

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"Length of the Square 0 km ... 4 km, default 0.5 km  "
		QtGui.QLabel:
			setText:"0*2_4_6_8*#*2_4_6_8*1*2_4_6_8*#*2_4_6_8*2*2_4_6_8*#*2_4_6_8*3*2_4_6_8*#*2_4_6_8*4"
		QtGui.QSlider:
			id:'s'
			setOrientation: PySide.QtCore.Qt.Orientation.Horizontal
			setMinimum: 0
			setMaximum: 40
			setTickInterval: 1
			setValue: 2
			setTickPosition: QtGui.QSlider.TicksBothSides

		QtGui.QPushButton:
			setText: "Run values"
			clicked.connect: app.runbl

		QtGui.QPushButton:
			setText: "Show openstreet map in web browser"
			clicked.connect: app.showMap

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"P R E D E F I N E D   L O C A T I O N S"
		QtGui.QLabel:

		QtGui.QRadioButton:
			setText: "Sonneberg Outdoor Inn"
			clicked.connect: app.run_sternwarte

		QtGui.QRadioButton:
			setText: "Coburg university and school "
			clicked.connect: app.run_co2

		QtGui.QRadioButton:
			setText: "Berlin Alexanderplatz/Haus des Lehrers"
			clicked.connect: app.run_alex

		QtGui.QRadioButton:
			setText: "Berlin Spandau"
			clicked.connect: app.run_spandau

		QtGui.QRadioButton:
			setText: "Paris Rue de Seine"
			clicked.connect: app.run_paris

		QtGui.QRadioButton:
			setText: "Tokyo near tower"
			clicked.connect: app.run_tokyo

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"P R O C E S S I N G:"
			id: "status"

		QtGui.QLabel:
			setText:"---"
			id: "status"

		QtGui.QProgressBar:
			id: "progb"

'''


class MyApp(object):

	def runXX(self):
		print "run app"
		print self
		s=self.root.ids['otto']
		print s
		s.setText('huhwas')
		pb=self.root.ids['progb']
		print s
		v=pb.value()
		pb.setValue(v+5)

	def run(self,b,l):
		s=self.root.ids['s'].value()
		key="%0.7f" %(b) + "," + "%0.7f" %(l)
		self.root.ids['bl'].setText(key)
		import_osm(b,l,float(s)/10,self.root.ids['progb'],self.root.ids['status'])

	def run_alex(self):
		self.run(52.52128,l=13.41646)

	def run_paris(self):
		self.run(48.85167,2.33669)

	def run_tokyo(self):
		self.run(35.65905,139.74991)

	def run_spandau(self):
		self.run(52.508,13.18)

	def run_co2(self):
		self.run(50.2631171, 10.9483)

	def run_sternwarte(self):
		self.run(50.3736049,11.191643)

	def runbl(self):
		print "Run values"
		bl=self.root.ids['bl'].text()
		spli=bl.split(',')
		b=float(spli[0])
		l=float(spli[1])
		s=self.root.ids['s'].value()
		elevation=self.root.ids['elevation'].isChecked()
		print [l,b,s]
		import_osm2(float(b),float(l),float(s)/10,self.root.ids['progb'],self.root.ids['status'],elevation)

	def showMap(self):
		print "Run values"
		bl=self.root.ids['bl'].text()
		spli=bl.split(',')
		b=float(spli[0])
		l=float(spli[1])
		s=self.root.ids['s'].value()
		print [l,b,s]
		WebGui.openBrowser( "http://www.openstreetmap.org/#map=16/"+str(b)+'/'+str(l))


def dialog():
	app=MyApp()

	import geodat.miki as miki
	reload(miki)


	miki=miki.Miki()
	miki.app=app
	app.root=miki

	miki.parse2(s6)
	miki.run(s6)


