#!/usr/bin/python
# -*- coding: utf-8 -*-

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from libs.lib import struct, distance, distancetoline, distancetopoint
import sys
import copy
import math
from libs.shapeType import shapeTypes

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
        self.params = struct(
            area = None
        )

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

    def isClosed(self):
        return self._closed

    def setOpen(self):
        self._closed = False

    # criterion for shape to close
    def toClose(self):
        return True if len(self.points) >= 4 else False

    # def reachMaxPoints(self):
    #     if len(self.points) >= 4:
    #         return True
    #     return False

    def updateParams(self):  # only for templating
        # if self.toClose():
        #     pass
        # else:
            pass

    def addPoint(self, point):
        if not self.toClose():
            self.points.append(point)

    def popPoint(self):
        if self.points:
            return self.points.pop()
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
        for i, p in enumerate(self.points):
            if distance(p - point) <= epsilon:
                return i
        return None

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

    def copy(self):
        shape = Shape("%s" % self.label)
        shape.points = [p for p in self.points]
        shape.fill = self.fill
        shape.selected = self.selected
        shape._closed = self._closed
        if self.line_color != Shape.line_color:
            shape.line_color = self.line_color
        if self.fill_color != Shape.fill_color:
            shape.fill_color = self.fill_color
        shape.difficult = self.difficult
        return shape

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
        self.shapeType = shapeTypes.box
        self.params = struct(
            area = None
        )

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

    def isClosed(self):
        return self._closed

    def setOpen(self):
        self._closed = False

    # criterion for shape to close
    def toClose(self):
        return True if len(self.points) >= 4 else False

    # def reachMaxPoints(self):
    #     if len(self.points) >= 4:
    #         return True
    #     return False

    def updateParams(self):  # only for templating
        # if self.toClose():
        #     pass
        # else:
            pass

    def addPoint(self, point):
        if not self.toClose():
            self.points.append(point)

    def popPoint(self):
        if self.points:
            return self.points.pop()
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
        for i, p in enumerate(self.points):
            if distance(p - point) <= epsilon:
                return i
        return None

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

    def copy(self):
        shape = Shape("%s" % self.label)
        shape.points = [p for p in self.points]
        shape.fill = self.fill
        shape.selected = self.selected
        shape._closed = self._closed
        if self.line_color != Shape.line_color:
            shape.line_color = self.line_color
        if self.fill_color != Shape.fill_color:
            shape.fill_color = self.fill_color
        shape.difficult = self.difficult
        return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value


# Line class inherited from Shape class
class Line(Shape):

    def __init__(self, line_color=None):
        super(Line,self).__init__(line_color=line_color)

        self.shapeType = shapeTypes.line
        self.params = struct(
            length = None
        )
        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }
        self._closed = False

    # criterion for shape to close
    def toClose(self):
        return True if len(self.points) >= 2 else False

    def updateParams(self):
        if self.toClose():
            self.params.length = distancetopoint(self.points[0], self.points[1])
        else:
            self.params.length = None

    def addPoint(self, point):
        if not self.toClose():
            self.points.append(point)
            if self.toClose():
                self.close()
                self.updateParams()

    def popPoint(self):
        if self.points:
            pop = self.points.pop()
            self.setOpen()
            self.updateParams()
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

    def nearestEdge(self, point, epsilon):
        return None

    def containsPoint(self, point):
        return None

    def makePath(self):
        path = QPainterPath(self.points[0])
        if len(self.points) > 1:
            for p in self.points[1:]:
                path.lineTo(p)
            return path
        else:
            return None

    def boundingRect(self):
        return self.makePath().boundingRect()

    def updateLength(self):
        if len(self.points) != 2:
            return None
        p1, p2 = self.points
        self.length = distancetopoint(p1, p2)
        return self.length

class Polygon(Shape):

    def __init__(self, line_color=None):
        super(Polygon,self).__init__(line_color=line_color)

        self.shapeType = shapeTypes.polygon
        self.params = struct(
            area = None
        )
        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }
        self._closed = False

    def toClose(self, eps = 10):
        return True \
            if (len(self.points) != 2 and 
                distancetopoint(self.points[-1], self.points[0]) < eps) \
            else False

    def updateParams(self):
        # if self.toClose():
        #     self.params.area = distancetopoint(self.points[0], self.points[1])
        # else:
            # self.params.area = None
        pass

    def addPoint(self, point):
        if self.toClose():
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
            radius = None,
            longAxis = None,
            shortAxis = None,
            roundity = None
        )
        self._highlightIndex = None
        self._highlightMode = self.NEAR_VERTEX
        self._highlightSettings = {
            self.NEAR_VERTEX: (4, self.P_ROUND),
            self.MOVE_VERTEX: (1.5, self.P_SQUARE),
        }
        self._closed = False
        # if sorted, long axis should before short one,
        # change to False when ellipse created and adjusted
        # self._sortedAxes = False

    # criterion for shape to close
    # points num == 4
    # points cannot be too close
    # have intercept point of the two segments
    def toClose(self):
        if (self.tooClose(self, point) or
            self.tooMany(self, point) or
            self.intersept(self, point) is None):
            return False
        if not self.tooMany():  #  len(self.points) <= 3
            if len(self.points) == 3:
                if self.intersept(self.points, point):
                    return True
                else:
                    # this is implemented in self.setOpen func,
                    # so I comment it. OK to uncomment
                    # self.params.center = None  
                    return False
            else:
                return False

    def tooClose(self, point, eps=10):
        for p in self.points:
            if distancetopoint(point, p) < eps:
                return True
        return False

    def tooMany(self):
        return True if len(self.points) >= 4 else False

    # this function is in updateCenter, I do not insulate it 
    # because I want to avoid duplicated calculation 
    # when calculate the center point
    # 为了避免重复计算，将这个函数设计为可以直接更新 self.center，
    # 故在作为判断条件使用时，需要在返回值为False时候，补充把self
    # 我们再在调用的使用额外把self.param.center= None
    def intersept(self, point, k_lower=-0.1, k_upper=0.1, eps=3):
        assert len(self.points) == 3
        def slope(p1, p2):
            return (p1.y()-p2.y())/(p1.x()-p2.x())

        def substitution(p1,p2,x=None,y=None):
            assert ((x is not None) and (y is None)) or ((x is None) and (y is not None))
            k = slope(p1,p2)
            b = p1.y() - k * p1.x()
            if x:
                return QPointF(x, k*x + b) if (y is None) else None
            elif y:
                return QPointF((y-b)/k, y)
            return None
        
        def withinSegment(p1,p2,inter):
            return (p1.x() - inter.x()) * (p2.x() - inter.x()) < 0 and \
                    (p1.y() - inter.y()) * (p2.y() - inter.y())

        def isHorizontal(slope, lower=k_lower, upper=k_upper):
            if lower < slope < upper:
                return True
            return False
        
        def isVertical(slope, lower=k_lower, upper=k_upper):
            return isHorizontal(1/slope, lower, upper)

        p1, p2, p3, p4 = *self.points, point
        dx1 = abs(p1.x() - p2.x())
        dx2 = abs(p3.x() - p4.x())

        if (dx1 <= eps) and (dx2 <= eps):  # parallel vertically
            return False
        if dx1 <= eps:
            center = QPointF(p1.x(), substitution(p3, p4, x=p1.x()))
            if withinSegment(p3, p4, center):
                self.params.center = center
                return True
            else:
                return False
        if dx2 <= eps:
            center = QPointF(p3.x(), substitution(p1, p2, x=p3.x()))
            if withinSegment(p1, p2, center):
                self.params.center = center
                return True
            else:
                return False

        k1 = slope(p1, p2)
        k2 = slope(p3, p4)

        if isVertical(k1) and isVertical(k2):
            return False
        elif isHorizontal(k1) and isHorizontal(k2):
            return False
        
        center_x = (p1.x()*k1 - p3.x()*k2 + p3.y() - p1.y()) / (k1 - k2)
        center_y = (center_x - p1.x()) * k1 + p1.y()
        center = QPointF(center_x, center_y)
        if (withinSegment(p1,p2,center) and withinSegment(p3,p4,center)):
            self.params.center = center
            return True
        else:
            return False

    # this func cannot be called unless intercept()==True
    def updateParams(self):
        p1, p2, p3, p4 = self.points
        l1 = distancetopoint(p1,p2)
        l2 = distancetopoint(p3,p4)
        self.params.longAxis, self.params.shortAxis, self.params.roundity = (l1, l2, l1/l2) \
            if l1 > l2 \
            else (l2, l1, l2/l1)
        self.radius = math.sqrt(l1 * l2) / 2

    def nullifyParams(self):
            self.params.center = None
            self.params.radius = None
            self.params.longAxis = None
            self.params.shortAxis = None
            self.params.roundity = None

    def addPoint(self, point):
        if (not self.tooClose(self, point) and 
            not self.tooMany(self, point) and
            self.intersept(self, point)):
            return
        if not self.tooMany():  #  len(self.points) <= 3
            if len(self.points) == 3:
                if self.intersept(self.points, point):
                    self.points.append(point)
                    self.updateParams()
                else:
                    # this is implemented in self.setOpen func,
                    # so I comment it. OK to uncomment
                    # self.params.center = None  
                    self.points = []
                    self.setOpen()
            else:
                self.points.append(point)
        # if self.toClose():


    def popPoint(self):
        if self.points:
            self.setOpen()
            return self.points.pop()
        return None

    def setOpen(self):
        self._closed = False
        self.nullifyParams()

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

            if len(self.points) == 2:
                line_path.lineTo(self.points[1])
            if len(self.points) == 4:
                line_path.lineTo(self.points[1])
                line_path.moveTo(self.points[2])
                line_path.lineTo(self.points[3])

            for i, p in enumerate(self.points):
                self.drawVertex(vrtx_path, i)

            if self.isClosed():
                ellipse_path.addEllipse(self.center, self.radius, self.radius)

            painter.drawPath(line_path)
            painter.drawPath(vrtx_path)
            painter.fillPath(vrtx_path, self.vertex_fill_color)
            painter.drawPath(ellipse_path)

            if self.fill:
                color = self.select_fill_color if self.selected else self.fill_color
                painter.fillPath(ellipse_path, color)
    
    def nearestEdge(self, point, epsilon):
        return None

    def makePath(self):
        path = QPainterPath(self.points[0])

        if self.isClosed():
            path.addEllipse(self.center, self.radius, self.radius)
        else:
            if len(self.points) == 2:
                path.lineTo(self.points[1])
            if len(self.points) == 4:
                path.lineTo(self.points[1])
                path.moveTo(self.points[2])
                path.lineTo(self.points[3])

        return path




def shapeFactory(stype=shapeTypes.shape, shapeTypes=shapeTypes):
    if stype == shapeTypes.box:
        return Box
    if stype == shapeTypes.line:
        return Line
    if stype == shapeTypes.polygon:
        return Polygon
    if stype == shapeTypes.ellipse:
        return Ellipse

