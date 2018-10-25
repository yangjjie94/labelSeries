from libs.pascal_voc_io import XML_EXT
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from libs.labelFile import LabelFile, LabelFileError
from libs.shape import Shape, shapeFactory
from libs.shapeType import shapeTypes
from libs.ustr import ustr

class LabelsList():
    
    def __init__(self, imgList):
        self.imgPathList = imgList
        self.total = len(self.imgPathList)
        self.labelslist = [None for _ in range(self.total)]
        LabelsList.LOAD_WHEN_INIT = 10
        LabelsList.JPG_EXT = '.jpg'
        self.upperbound = LabelsList.LOAD_WHEN_INIT
        self.inc = 10
        self.load(LabelsList.LOAD_WHEN_INIT) 

    def __getitem__(self, n):
        return self.labelslist[n]

    def __setitem__(self, n, value):
        self.labelslist[n] = value

    def __delitem__(self, n):
        todelete = self.labelslist[n]
        self.labelslist[n] = None
        del(todelete)

    def load(self, nth):
        start = self.upperbound
        end = min(self.upperbound + self.inc, self.total) 
        if start >= end:
            return
        for i in range(start, end):
            self.load_each(i)

        self.upperbound += self.inc

    def load_each(self, index):
        filename = self.imgPathList[index]
        filename = filename[:len(filename)-len(LabelsList.JPG_EXT)] + XML_EXT
        if (self.labelslist[index] is not None):
            if self.updateLabelFile(filename):
                s = []
                shapes = self.labelFile.shapes
                shapeFac = shapeFactory()
                for shapeType, label, points, line_color, fill_color, difficult in shapes:
                    shapeFac.setType(shapeType)
                    shape = shapeFac.getShape()
                    shape.label = label
                    for x, y in points:
                        shape.addPoint(QPointF(x, y))
                    shape.difficult = difficult
                    shape.close()
                    s.append(shape)

                    # if line_color:
                    #     shape.line_color = QColor(*line_color)
                    # else:
                    #     shape.line_color = generateColorByText(label)

                    # if fill_color:
                    #     shape.fill_color = QColor(*fill_color)
                    # else:
                    #     shape.fill_color = generateColorByText(label)
                self.labelslist[index] = s

    def updateLabelFile(self, filename):
        unicodeFilePath = ustr(filename)
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    print("LabelFile: LabelFileError as e, 96")
                    return False
            else:
                self.labelFile = None
            return True
        else:
            return False