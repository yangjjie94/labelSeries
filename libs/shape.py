#!/usr/bin/python
# -*- coding: utf-8 -*-

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.lib import struct, distance, distancetoline, distancetopoint, averageDiameter
import sys
import copy
import math
from libs.shapeType import shapeTypes

import const

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)


class Shape(object):
    P_SQUARE, P_ROUND = range(2)

    MOVE_VERTEX, NEAR_VERTEX = range(2)

    # The following class variables influence the drawing
    # of _all_ shape objects.
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    hvertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR  # highlight vrtx
    point_type = P_ROUND
    point_size = 8
    scale = 1.0

    def __init__(self, label=None, line_color=None,difficult = False):
        self.label = label
        self.points = []
        self.fill = False
        self.selected = False
        self.difficult = difficult

        self.shapeType = shapeTypes.shape
        # self.params = struct(
        #     area = None
        # )

        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }
        self._closed = False

        if line_color is not None:
            # Override the class line_color attribute
            # with an object attribute. Currently this
            # is used for drawing the pending line a different color.
            self.line_color = line_color

    def close(self):
        self._closed = True

    # criterion for shape to close
    # def toClose(self):
    #     return True if len(self.points) >= 4 else False

    def reachMaxPoints(self):
        return True if len(self.points) >= 4 else False

    # def updateParams(self):  # only for templating
    #     # if self.toClose():
    #     #     pass
    #     # else:
    #         pass

    def addPoint(self, point):
        if not self.reachMaxPoints():
            self.points.append(point)

    def popPoint(self):
        if self.points:
            return self.points.pop()
        return None

    def insertPoint(self, i, point):
        # self.points.insert(i, point)
        pass

    def isClosed(self):
        return self._closed

    def setOpen(self):
        self._closed = False


    def paint(self, painter):
        if self.points:
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vrtx_path = QPainterPath()

            line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            #self.drawVertex(vrtx_path, 0)

            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                self.drawVertex(vrtx_path, i)
            if self.isClosed():
                line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)

            # Draw text at the top-left
            # min_x = sys.maxsize
            # min_y = sys.maxsize
            # for point in self.points:
            #     min_x = min(min_x, point.x())
            #     min_y = min(min_y, point.y())
            # if min_x != sys.maxsize and min_y != sys.maxsize:
            #     font = QFont()
            #     font.setPointSize(8)
            #     font.setBold(True)
            #     painter.setFont(font)
            #     if(self.label == None):
            #         self.label = ""
            #     painter.drawText(min_x, min_y, self.label)

            if self.fill:
                color = self.select_fill_color if self.selected else self.fill_color
                painter.fillPath(line_path, color)

    def drawVertex(self, path, i):
        d = self.point_size / self.scale
        shape = self.point_type
        point = self.points[i]
        if i == self._highlightIndex:
            size, shape = self._highlightSettings[self._highlightMode]
            d *= size
        if self._highlightIndex is not None:
            self.vertex_fill_color = self.hvertex_fill_color
        else:
            self.vertex_fill_color = Shape.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)
        else:
            assert False, "unsupported vertex shape"

    def nearestVertex(self, point, epsilon):
        min_distance = float('inf')
        min_i = None
        for i, p in enumerate(self.points):
            dist = distance(p - point)
            if (dist <= epsilon and dist < min_distance):
                min_distance = dist
                min_i = i
        return min_i

    def nearestEdge(self, point, epsilon):
        min_distance = float('inf')
        post_i = None
        for i,_ in enumerate(self.points):
            line = [self.points[i - 1], self.points[i]]
            dist = distancetoline(point, line)
            if dist <= epsilon and dist < min_distance:
                return i-1  # ranging [-1, len(points) - 1 )
        return None

    def containsPoint(self, point):
        return self.makePath().contains(point)

    def makePath(self):
        path = QPainterPath(self.points[0])
        for p in self.points[1:]:
            path.lineTo(p)
        return path

    def boundingRect(self):
        return self.makePath().boundingRect()

    def moveBy(self, offset):
        self.points = [p + offset for p in self.points]

    def moveVertexBy(self, i, offset):
        self.points[i] = self.points[i] + offset

    def highlightVertex(self, i, action):
        self._highlightIndex = i
        self._highlightMode = action

    def highlightClear(self):
        self._highlightIndex = None

    # I use deepcopy instead, and this function is deprecated
    # def copy(self):
    #     shape = Shape("%s" % self.label)
    #     shape.points = [p for p in self.points]
    #     shape.fill = self.fill
    #     shape.selected = self.selected
    #     shape._closed = self._closed
    #     if self.line_color != Shape.line_color:
    #         shape.line_color = self.line_color
    #     if self.fill_color != Shape.fill_color:
    #         shape.fill_color = self.fill_color
    #     shape.difficult = self.difficult
    #     return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value


# Bounding Box class inherited from Shape class - 
# exactly the same actually
class Box(Shape):

    def __init__(self, label=None, line_color=None,difficult = False):
        super(Box, self).__init__()

        self.shapeType = shapeTypes.box
        # self.params = struct(
        #     area = None
        # )

# Line class inherited from Shape class
class Line(Shape):

    def __init__(self, line_color=None):
        super(Line,self).__init__(line_color=line_color)

        self.shapeType = shapeTypes.line
        # self.params = struct(
        #     length = None
        # )

    # criterion for shape to close
    def reachMaxPoints(self):
        return True if len(self.points) >= 2 else False

    # def updateParams(self):
    #     if self.reachMaxPoints():
    #         self.params.length = distancetopoint(self.points[0], self.points[1])
    #     else:
    #         self.params.length = None

    def addPoint(self, point):
        if not self.reachMaxPoints():
            self.points.append(point)
            if self.reachMaxPoints():
                self.close()
                # self.updateParams()

    def popPoint(self):
        if self.points:
            pop = self.points.pop()
            self.setOpen()
            # self.updateParams()
            return pop
        return None

    def paint(self, painter):
        if self.points:
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vrtx_path = QPainterPath()

            line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            #self.drawVertex(vrtx_path, 0)

            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                self.drawVertex(vrtx_path, i)

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            # painter.fillPath(vrtx_path, self.vertex_fill_color)

    def containsPoint(self, point):
        return False


class Polygon(Shape):

    def __init__(self, line_color=None):
        super(Polygon,self).__init__(line_color=line_color)

        self.shapeType = shapeTypes.polygon
        # self.params = struct(
        #     area = None
        # )
    
    def reachMaxPoints(self):
        return False

    # def updateParams(self):
    #     # if self.toClose():
    #     #     self.params.area = distancetopoint(self.points[0], self.points[1])
    #     # else:
    #         # self.params.area = None
    #     pass

    # 对于多边形来说，判断更为复杂，不能像前面一样利用 reachMaxPoints, 
    # 所以这个类中将reachMaxPoints 设定为恒返回 False，并引入新的判断函数，
    # 因为新的判断函数需要待加入的point辅助确定，所以我们新函数在addPoint函数中使用
    
    def addPoint(self, point):
        def toClose(self, point, eps = const.TOLERENCE):
            return True if self.points and point == self.points[0] else False
            # return True \
            #     if (len(self.points) != 2 and 
            #         distancetopoint(self.points[-1], self.points[0]) < eps) \
            #     else False

        if toClose(self, point):
            self.close()  # the last point (equal to points[0]) is not added
        else:
            self.points.append(point)
        
    def popPoint(self):
        if self.points:
            self.setOpen()
            return self.points.pop()
        return None

    def insertPoint(self, i, point):
        self.points.insert(i, point)

    def insertPoint(self, i, point):
        self.points.insert(i, point)

    def paint(self, painter):
        if self.points:
            color = self.select_line_color \
                if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vrtx_path = QPainterPath()

            line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            # self.drawVertex(vrtx_path, 0)

            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                self.drawVertex(vrtx_path, i)
            if self.isClosed():
                line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)
            if self.fill:
                color = self.select_fill_color \
                    if self.selected else self.fill_color
                painter.fillPath(line_path, color)

class Ellipse(Shape):

    def __init__(self, line_color=None):
        super(Ellipse,self).__init__(line_color=line_color)

        self.shapeType = shapeTypes.ellipse
        self.params = struct(
            center = None, 
            # radius = None,
            # longAxis = None,
            # shortAxis = None,
            # roundity = None
        )
        self.line = [QPointF(), QPointF()]  # a Python list: syncronized with self.line in Canvas()

    # criterion for shape to close
    # points num == 4
    # points cannot be too close
    # have intercept point of the two segments

    def reachMaxPoints(self):
        return True if len(self.points) >= 4 else False

    def addPoint(self, point):
        # if (
        #     # not self.tooClose(self, point) and 
        #     not self.reachMaxPoints(self, point)):
        #     return
        if not self.reachMaxPoints():  #  len(self.points) <= 3
            if len(self.points) % 2 == 0:
                self.line = [point, point]
            else:
                self.line[1] = point
            self.points.append(point)

            if self.reachMaxPoints():
                if self.getCenter() is not None:
                    self.close()
                else:
                    self.popPoint()
                    self.popPoint()

    def close(self):
        self._closed = True
        self.params.center = self.getCenter()
        assert self.params.center is not None

    def popPoint(self):
        if self.points:
            self.setOpen()
            return self.points.pop()
        return None

    # def toClose(self, point):
    #     if (self.reachMaxPoints(self) or
    #         # self.tooClose(self, point) or
    #         self.getCenter(point=point) is None):
    #         return False
    #     if not self.reachMaxPoints():  #  len(self.points) <= 3
    #         if len(self.points) == 3:
    #             if self.getCenter(point=point):
    #                 return True
    #             else:
    #                 # this is implemented in self.setOpen func,
    #                 # so I comment it. OK to uncomment
    #                 self.params.center = None  
    #                 return False
    #         else:
    #             return False


    def tooClose(self, point, eps=const.TOLERENCE):
        for p in self.points:
            if distancetopoint(point, p) < eps:
                return True
        return False


    # this function is in updateCenter, I do not insulate it 
    # because I want to avoid duplicated calculation 
    # when calculate the center point
    # 为了避免重复计算，将这个函数设计为可以直接更新 self.center，
    # 故在作为判断条件使用时，需要在返回值为False时候，补充把self
    # 我们再在调用的使用额外把self.param.center= None
    # intersept, 原来是返回True/False，输入参数是len=3的self.points 和 point
    def getCenter(self, line=None, point=None, points=None, k_lower=-0.1, k_upper=0.1, eps=const.TOLERENCE):

        def slope(p1, p2):
            return (p1.y()-p2.y())/(p1.x()-p2.x())

        def substitution(p1,p2,x=None,y=None):
            assert ((x is not None) and (y is None)) or ((x is None) and (y is not None))
            k = slope(p1,p2)
            b = p1.y() - k * p1.x()
            if x is not None:
                return QPointF(x, k*x + b) if (y is None) else None
            elif y is not None:
                return QPointF((y-b)/k, y)

        def withinArea(points, point):
            if not len(points) == 4:
                return False
            p1,p2,p3,p4 = points
            path = QPainterPath(p1)
            for p in [p3,p2,p4,p1]:
                path.lineTo(p)        
            return path.contains(point)

        if len(self.points) == 4:
            p1, p2, p3, p4 = self.points
        elif (len(self.points) == 3) and (line is not None):
            assert len(line) == 2
            p1, p2, p3, p4 = *self.points[:2], *line
        elif (len(self.points) == 3) and (point is not None):
            assert isinstance(point, QPointF)
            p1, p2, p3, p4 = *self.points, point
        elif self.isClosed() and points is not None:
            p1, p2, p3, p4 = points
        else:
            return None

        dx1 = abs(p1.x() - p2.x())
        dx2 = abs(p3.x() - p4.x())

        if (dx1 <= eps) and (dx2 <= eps):  # parallel vertically
            return None
        elif dx1 <= eps:
            center = QPointF(p1.x(), substitution(p3, p4, x=p1.x()).y())
        elif dx2 <= eps:
            center = QPointF(p3.x(), substitution(p1, p2, x=p3.x()).y())
        else:
            k1 = slope(p1, p2)
            k2 = slope(p3, p4)
            center_x = (p1.x()*k1 - p3.x()*k2 + p3.y() - p1.y()) / (k1 - k2)
            center_y = (center_x - p1.x()) * k1 + p1.y()
            center = QPointF(center_x, center_y)

        return center if withinArea(self.points, center) else None

    # this func cannot be called unless intercept()==True
    # def updateParams(self):
    #     p1, p2, p3, p4 = self.points
    #     l1 = distancetopoint(p1,p2)
    #     l2 = distancetopoint(p3,p4)
    #     self.params.longAxis, self.params.shortAxis, self.params.roundity = (l1, l2, l1/l2) \
    #         if l1 > l2 \
    #         else (l2, l1, l2/l1)
    #     self.radius = math.sqrt(l1 * l2) / 2

    # def nullifyParams(self):
    #         self.params.center = None
    #         self.params.radius = None
    #         self.params.longAxis = None
    #         self.params.shortAxis = None
    #         self.params.roundity = None

    def getDiameter(self):
        p1, p2, p3, p4 = self.points
        return averageDiameter(p1,p2,p3,p4)

    def setOpen(self):
        self._closed = False
        # self.nullifyParams()

    def paint(self, painter):
        if self.points:
            color = self.select_line_color if self.selected else self.line_color
            pen = QPen(color)
            # Try using integer sizes for smoother drawing(?)
            pen.setWidth(max(1, int(round(2.0 / self.scale))))
            painter.setPen(pen)

            line_path = QPainterPath()
            vrtx_path = QPainterPath()
            ellipse_path = QPainterPath()

            line_path.moveTo(self.points[0])
            # Uncommenting the following line will draw 2 paths
            # for the 1st vertex, and make it non-filled, which
            # may be desirable.
            #self.drawVertex(vrtx_path, 0)

            if len(self.points) in (2,3):
                line_path.lineTo(self.points[1])
            elif len(self.points) == 4:
                line_path.lineTo(self.points[1])
                line_path.moveTo(self.points[2])
                line_path.lineTo(self.points[3])

            for i, p in enumerate(self.points):
                self.drawVertex(vrtx_path, i)

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)

            if self.isClosed() or self.getCenter() or self.getCenter(self.line):
                path = self.makePath()
                if path is not None:
                    painter.drawPath(path)

            if self.fill:
                color = self.select_fill_color if self.selected else self.fill_color
                if path is not None:
                    painter.fillPath(path, color)
    
    def nearestEdge(self, point, epsilon):
        return None

    def makePath(self, line=None):

        def BezierEllipse(points, center=None):
            assert len(self.points) == 4

            p1,p2,p3,p4 = self.points

            a, b = distancetopoint(p1, p2), distancetopoint(p3, p4)
            if b > a:
                a, b = b, a 
                p1,p2,p3,p4 = p3,p4,p1,p2
            
            if center is not None:
                center = self.getCenter()
                if center is None:
                    return None
            
            path = QPainterPath()
            path.moveTo(p1.x(), p1.y())
            for pt1, pt2 in zip([p1,p3,p2,p4],[p3,p2,p4,p1]):
                d1 = pt1 - center
                d2 = pt2 - center
                # 关键是bezierCurveTo中两个控制点的设置
                # 0.5和0.6是两个关键系数（在本函数中为试验而得）
                if distance(d2) > distance(d1):
                    path.cubicTo(0.5*d2.x()+pt1.x(), 0.5*d2.y()+pt1.y(), 
                                0.6*d1.x()+pt2.x(), 0.6*d1.y()+pt2.y(), 
                                pt2.x(), pt2.y())
                else:
                    path.cubicTo(0.6*d2.x()+pt1.x(), 0.6*d2.y()+pt1.y(), 
                                0.5*d1.x()+pt2.x(), 0.5*d1.y()+pt2.y(), 
                                pt2.x(), pt2.y())    
            return path
        if line is None:
            if self.isClosed() or len(self.points) == 4:
                assert len(self.points) == 4 and self.params.center is not None
                path = BezierEllipse(self.points,self.params.center)
            else:
                return None
        elif len(self.points) == 2:
            path = BezierEllipse(self.points+line.points)
        else:
            return None
        return path

class shapeFactory(object):
    def __init__(self):
        self.shapeTypes = shapeTypes
        # self.shapeTypeList = filter(lambda x: x[:2] != '__', dir(self.shapeTypes))
        isItem = lambda x: x[:2] != '__'
        self.shapeTypeList = list(item for item in dir(self.shapeTypes) if isItem(item))
        self._shapeType = self.shapeTypes.shape

    def setType(self, st):
        if st in self.shapeTypeList:

            self._shapeType = st
        else:
            raise ValueError("shapeFactory::setType: not a shapeType")

    def getShape(self):
        if self._shapeType == shapeTypes.box:
            return Box()
        if self._shapeType == shapeTypes.line:
            return Line()
        if self._shapeType == shapeTypes.polygon:
            return Polygon()
        if self._shapeType == shapeTypes.ellipse:
            return Ellipse()

        return Shape()

    def isType(self, st):
        return st == self._shapeType

