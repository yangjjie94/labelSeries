#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from libs.labelFile import LabelFile, LabelFileError
from libs.shape import Shape, shapeFactory
from libs.shapeType import shapeTypes
from libs.ustr import ustr
import const
import os
from PyQt5.QtCore import pyqtSignal, QObject, QPointF, QTimer, QThread
from PyQt5.QtGui import QColor
from libs.lib import generateColorByText
from math import ceil

class LabelsCache(QThread):
    
    def __init__(self, imgList):
        super(LabelsCache, self).__init__()
        self.imgPathList = imgList
        self.total = len(self.imgPathList)
        self.labels_cache = [None for _ in range(self.total)]
        self.indices = []

        self.begin = 0
        self._stop = False

    def run(self):

        self.update(0, const.UPDATE_STEP)
        for i in range(ceil((self.total-const.LOAD_WHEN_INIT)/const.UPDATE_STEP) + 1):
            self.update()

    def __len__(self):
        return len(self.imgPathList)

    def __getitem__(self, n):
        if self.labels_cache[n] is None:
            self.load_each(n)
        return self.labels_cache[n]

    def __setitem__(self, n, value):
        self.labels_cache[n] = value

    def __delitem__(self, n):
        to_del, self.labels_cache[n] = self.labels_cache[n], None
        del(to_del)

    def update(self, start=None, stop=None):
        begin = max(start, 0) if start is not None else self.begin
        end = stop if stop is not None else min(begin + const.UPDATE_STEP, self.total)
        for i in range(begin, end):
            self.load_each(i)

        if end >= self.total:
            self.stop()
            return

        self.begin = end

        assert len(self) == self.total, "deletion on mistake"

    def load_each(self, index):
        filename = self.imgPathList[index]
        filename = filename[:len(filename)-len(const.JPG_EXT)] + const.XML_EXT
        if (self.labels_cache[index] is not None):
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
                    if line_color:
                        shape.line_color = QColor(*line_color)
                    else:
                        shape.line_color = generateColorByText(label)

                    if fill_color:
                        shape.fill_color = QColor(*fill_color)
                    else:
                        shape.fill_color = generateColorByText(label)
                
                    s.append(shape)
                self.labels_cache[index] = s

                self.indices.append(index)

    def updateLabelFile(self, filename):
        unicodeFilePath = ustr(filename)
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    print("LabelFile: LabelFileError")
                    return False
            else:
                self.labelFile = None
            return True
        else:
            return False

    def stop(self):
        self._stop = True

    def stopped(self):
        return self._stop
    
