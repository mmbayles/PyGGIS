#!/usr/bin/env python
# -*- coding: utf-8 -*-
##Copyright 2009, 2010 Владимир Суханов 
"""
Утилиты и функции для ГГИС: 
getPoints, pars_geometry, makeLINESTRING, distance2d
"""
from OCC.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
import wx
import wx.grid
import psycopg2
import OCC
from OCC.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCC.GeomAbs import GeomAbs_Arc
from OCC import STEPControl, StlAPI, IGESControl, TopoDS, BRep, BRepTools
#from OCC.AIS import AIS_Shape
from OCC.BRepBuilderAPI import *
from OCC.gp import *
from regim import *
from utils import *
from math import *
from scipy import *
from scipy import linalg
from addons.ShapeToTopology import ShapeToTopology
from OCC.TopAbs import *
from OCC.TopExp import *

from OCC.TColgp import *
from OCC.GeomAPI import *


def GetRowsTbl(tableName, where=""):
    conn = psycopg2.connect("dbname="+POSTGR_DBN+" user="+POSTGR_USR)
    curs = conn.cursor()
    query = "select * from " + tableName
    if where:
        query = query + " where " + where
    curs.execute(query)
    rows = curs.fetchall()
    return rows

def get_model_center():
    return [9735, 10087]  # временно

def pars_geometry(geom):
    """Разобрать координаты геометрического объекта"""
    coords = geom[geom.find('(')+1:geom.find(')')]
    lstCoords = coords.split(',')
    lstXYZ = []
    for pnt in lstCoords:
        pntXYZ = []
        xyz = pnt.split(' ')
        for val in xyz:
            pntXYZ = pntXYZ + [float(val)]
        lstXYZ = lstXYZ + [pntXYZ]
    return lstXYZ
        
def getPoints(shape):
    """Получить точки выбранного объекта"""
    result = []
    if shape:
        ex = TopExp_Explorer()
        ex.Init(shape, TopAbs_VERTEX)
        te = ShapeToTopology()
        bt = OCC.BRep.BRep_Tool
        result = []
        while True:
            sv = ex.Current()
            vv = te(sv)
            p1 = OCC.BRep.BRep_Tool.Pnt(vv)
            p1 = [p1.X(), p1.Y(), p1.Z()]
            if (len(result) == 0) or (p1 != result[-1]):
                result = result + [p1]
            sv = ex.Next()
            if not ex.More():
                break
    return result


def makeLINESTRING(pnts):
    geom = "GeomFromEWKT('SRID=-1;LINESTRING("
    j = 0
    for p in pnts:
        if j > 0:
            geom += ","
        j = 1
        geom += "%.0f %.0f %.0f"%(p[0],p[1],p[2])
    geom += ")')"
    return geom


def distance2d(p1,p2):
    return sqrt((p1[0]-p2[0])*(p1[0]-p2[0]) + (p1[1]-p2[1])*(p1[1]-p2[1]))


def distance3d(p1,p2):
    return sqrt((p1[0]-p2[0])*(p1[0]-p2[0]) + (p1[1]-p2[1])*(p1[1]-p2[1]) + (p1[2]-p2[2])*(p1[2]-p2[2]))


def getMNK(cloud, offset=[0, 0]):    #  [[x,y,z],...]
    """ Поиск линейной аппроксимации облака точек cloud = [[x,y,z], ...]
    z = b0 + b1*x + b2*y
    результат коэффициенты полинома:
    B = [ b0 ,  b1 , b2 ]
    b0 = B[0,0]; b1 = B[1,0]; b2 = B[2,0] 
    [b0,b1,b2]  
    """
    res = []
    xc = offset[0]; yc = offset[1]
    nCloud = len(cloud)
    if nCloud < 3:
        #print "Нет решения для ", cloud 
        return res
    sz = 0.0; zz = 0.0; zx = 0.0; zy = 0.0; sx = 0.0; sy = 0.0; xx = 0.0; yy = 0.0; xy = 0.0
    for point in cloud:
        x,y,z = point
        x = x - xc; y = y - yc
        sx = sx + x
        sy = sy + y
        sz = sz + z
        zz = zz + z*z
        zx = zx + z*x
        zy = zy + z*y
        xx = xx + x*x
        yy = yy + y*y
        xy = xy + x*y
    D = matrix([[sz], [zx], [zy]])
    A = matrix([[nCloud, sx, sy], [sx, xx, xy], [sy, xy, yy] ])
    try:
        res = linalg.solve(A, D)
        res = [res[0, 0], res[1, 0], res[2, 0]]
    except:
        res = []
        #print "Нет решения для ", cloud   
    return res

def getGrad(pnt, cloud):
    grad = [0.0, 0.0]
    n = 0
    for p in cloud:
        if p != pnt:
            dist = distance2d(pnt,p)
            if dist > 0.001:
                grP = (p[2]-pnt[2])/dist
                grPx = grP * (p[0]-pnt[0]) / dist
                grPy = grP * (p[1]-pnt[1]) / dist
                grad[0] += grPx
                grad[1] += grPy
                n += 1
    if n > 0:
        grad[0] /= n
        grad[1] /= n
    return grad            
                
def getNear(pnt, cloud):
    near = []
    if cloud:
        near = cloud[0]
        for p in cloud[1:]:
            if distance2d(pnt, p) < distance2d(pnt, near):
                near = p
    return near            


#Points coords configuration dialog
class CoordsDlg(wx.Dialog):
    def __init__(self,parent,ID,title,coords=[],
                 size=wx.DefaultSize, pos=wx.DefaultPosition,
                 style=wx.DEFAULT_DIALOG_STYLE):
        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, ID, title, pos, (570,300), style)
        self.this = pre.this        

        self.panel2 = wx.BoxSizer(wx.HORIZONTAL)
        
        AddLineBtn=wx.Button(self, -1, "Добавить точку")
        self.Bind(wx.EVT_BUTTON, self.OnAddLine, AddLineBtn)
        self.panel2.Add(AddLineBtn)

        DelLineBtn=wx.Button(self, -1, "Удалить точку")
        self.Bind(wx.EVT_BUTTON, self.OnDelLines, DelLineBtn)
        self.panel2.Add(DelLineBtn)

        self.panel3 = wx.BoxSizer(wx.HORIZONTAL)
        CloseBtn=wx.Button(self, -1, "Закрыть без сохранения")
        self.Bind(wx.EVT_BUTTON, self.OnClose, CloseBtn)
        self.panel3.Add(CloseBtn)
        SaveBtn=wx.Button(self, -1, "Сохранить")
        self.Bind(wx.EVT_BUTTON, self.OnSave, SaveBtn)
        self.panel3.Add(SaveBtn)

        self.panel1 = wx.BoxSizer(wx.VERTICAL)
        self.grid=wx.grid.Grid(self, -1,size=(570,260),name = "Coords")
        self.grid.CreateGrid(1,3,1)
        self.grid.SetColLabelValue(0,"x")
        self.grid.SetColLabelValue(1,"y")
        self.grid.SetColLabelValue(2,"z")
        #self.Bind(wx.grid.EVT_GRID_CELL_CHANGE,self.OnCellChange,self.grid)
        self.panel1.Add(self.grid,0, wx.EXPAND)
        self.panel1.Add(self.panel2, 0, wx.EXPAND)

        self.superMainPanel = wx.BoxSizer(wx.VERTICAL)
        self.superMainPanel.Add(self.panel1)
        self.superMainPanel.Add(self.panel3)
        self.SetSizer(self.superMainPanel)
        self.SetAutoLayout(1)
        self.superMainPanel.Fit(self)
        
        self.grid.ClearGrid()
        self.grid.DeleteRows(0, self.grid.GetNumberRows(),True)
        for i in xrange(len(coords)):
            self.grid.AppendRows(1,True)
            for j in xrange(3):
                if coords[i][j]=='':
                    self.grid.SetCellValue(i,j,'0')
                else:
                    self.grid.SetCellValue(i,j,str(coords[i][j]))

        self.save=False                
        
    def OnAddLine(self, event):
        self.grid.AppendRows(1,True)

    def OnDelLines(self, event):
        self.grid.DeleteRows(self.grid.GetNumberRows()-1, 1, True)

    def OnClose(self, event):
        self.Close()

    def OnSave(self, event):
        self.save = True
        self.Close()

    def ret(self):
        result = []
        for i in xrange(self.grid.GetNumberRows()):
            result.append([0, 0, 0])
            for j in xrange(3):
                if not self.grid.GetCellValue(i,j)=='':
                    result[i][j] = float(self.grid.GetCellValue(i,j))
        return result


"""def make_offset(wire, d, h=0):
    offset = BRepOffsetAPI_MakeOffset(wire,GeomAbs_Arc )
    offset.Perform(d, h)
    return offset.Shape()"""

def make_offset(shape, offset, height=0, round=True, close=True):
    offset *=- 1
    pnts = getPoints(shape)
    pnts_new = []
    Close = False
    if pnts[0] == pnts[-1]:
        Close = True
        pnts.pop()
    triangles = getTriangles(pnts, close)
    for i, v in enumerate(triangles):
        a=measure_angle(v[0],v[1],v[2])
        if v[2][0] >= v[1][0]:
            #b=measure_angle([v[0][0]+20,v[0][1],v[0][2]],v[0],v[1])
            b = measure_angle([v[1][0],v[1][1]+20,v[1][2]],v[1],v[2])
        else:
            b = measure_angle([v[1][0],v[1][1]-20,v[1][2]],v[1],v[2])+math.pi
        #print '-=-=-=-=-'
        #print math.degrees(a)
        #print math.degrees(b)
        #print math.degrees(tmp)
        if offset < 0 and round:
            #print 'a=',math.degrees(a),', b=', math.degrees(b)
            pnts_new.append(polar(pnts[i],b+a-math.pi/2,offset,height))
            pnts_new.append(polar(pnts[i],b+a/2,offset,height))
            pnts_new.append(polar(pnts[i],b+math.pi/2,offset,height))
        elif not round and (i == 0 or i == len(triangles)-1):
            if i == 0:
                if offset < 0:
                    pnts_new.append(polar(pnts[i],b+a-math.pi/2,offset,height))
                else:
                    pnts_new.append(polar(pnts[i],b+a-math.pi/2,offset,height))
            else:
                if offset < 0:
                    pnts_new.append(polar(pnts[i],b-math.pi/2,offset,height))
                else:
                    pnts_new.append(polar(pnts[i],b+math.pi*2,offset,height))
        else:
            pnts_new.append(polar(pnts[i],b+a/2,offset,height))
        #pnts_new.append(polar(pnts[i],b+a/2,offset,height))
    plgn = BRepBuilderAPI_MakePolygon()
    for pnt1 in pnts_new:
        plgn.Add(gp_Pnt(pnt1[0], pnt1[1], pnt1[2]))
    if Close:
        plgn.Close()
    #print dir(plgn)
    return plgn.Wire()


def getTriangles(pnts,close):
    l = len(pnts)
    triangles = []
    if close:
        triangles.append([pnts[-1],pnts[0],pnts[1]])
    else:
        triangles.append([continueLine(pnts[0],1),pnts[0],pnts[1]])
    for i in xrange(l-2):
        tmp = [pnts[i], pnts[i+1], pnts[i+2]]
        triangles.append(tmp)
    if close:
        triangles.append([pnts[-2],pnts[-1],pnts[0]])
    else:
        triangles.append([continueLine(pnts[-1],1),pnts[-1],pnts[0]])
    return triangles


def polar(point, angle, dist, height=0):
    #if angle>math.pi:
        #angle=angle-math.pi
    return [sin(angle) * dist + point[0],cos(angle) * dist + point[1],point[2]+height]


def measure_angle(p1,p2,p3):
    l1=distance2d(p1,p2)
    #print 'distance between ',p1,' and ',p2,' is ',l1
    l2=distance2d(p2,p3)
    #print 'distance between ',p2,' and ',p3,' is ',l2
    l3=distance2d(p1,p3)
    #print 'distance between ',p1,' and ',p3,' is ',l3
    #print "-===================-"
    #print l1, l2, l3
    tmp1=((l1*l1+l2*l2)-l3*l3)
    tmp2=(2*l1*l2)
    #print tmp1,tmp2,tmp1/tmp2
    return math.acos(tmp1/tmp2)


def Interpolate(pnts):
    print pnts
    array = TColgp_HArray1OfPnt(1, len(pnts))
    for i, v in enumerate(pnts):
        print v
        array.SetValue(i+1, gp_Pnt(v[0],v[1],v[2]))
    print array.Length()
    anInterpolation = GeomAPI_Interpolate(array.GetHandle(),True,1)
    anInterpolation.Perform()
    cu = anInterpolation.Curve()
    spline = BRepBuilderAPI_MakeEdge(cu)
    spline.Build()
    return spline.Shape()


def continueLine(pnt, l):
    newpnt = [0, 0, 0]
    if pnt[0] < 0:
        newpnt[0] = pnt[0]-l
    else:
        newpnt[0] = pnt[0]+l
    if pnt[1] < 0:
        newpnt[1] = pnt[1]-l
    else:
        newpnt[1] = pnt[1]+l
    newpnt[2] = pnt[2]
    return newpnt


def length(pnts):
    l = 0
    for i in xrange(len(pnts)-1):
        l += distance3d(pnts[i], pnts[i+1])
    print l
    return l


def getGrided(coord,gridSize):
    per = coord%gridSize
    if per < gridSize/2:
        return coord-per
    else:
        return coord+(gridSize-per)


def invert(obj):
    pnts = getPoints(obj)
    plgn = BRepBuilderAPI_MakePolygon()
    for i in range(len(pnts)-1, -1, -1):
        plgn.Add(gp_Pnt(pnts[i][0], pnts[i][1], pnts[i][2]))
    return plgn.Wire()