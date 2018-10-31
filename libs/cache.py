#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from math import floor, ceil
from PyQt5.QtGui import QImage
import qimage2ndarray
import numpy as np
import const
from PyQt5.QtCore import pyqtSignal, QObject

def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default

class Cache(QObject):
    update_around = pyqtSignal(int)

    def __init__(self, imgList):
        super(Cache, self).__init__()
        if imgList is None or len(imgList) == 0:
            return None
        self.imgPathList = imgList
        self.total = len(self.imgPathList)
        self.data = [None for _ in range(self.total)]

        self.update_around.connect(self.update)
        self.scope = (0, const.LOAD_WHEN_INIT)

    def start(self):
        self.update(0, const.LOAD_WHEN_INIT)
        

    def __len__(self):
        return len(self.data)

    def __getitem__(self,i):
        if self.data[i] is None:
            self.load_each(i)

        self.update_around.emit(i-const.UPDATE_STEP)
        return self.data[i]

    def __setitem__(self, i, image):
        self.data[i] = image

    def __delitem__(self, i):
        to_del, self.data[i] = self.data[i], None
        del to_del

    def update(self, start, stop=None):
        
        begin = max(start, 0)
        end = stop if stop is not None else min(start + 2 * const.UPDATE_STEP, self.total)
        if (self.scope[1] <= begin) or (self.scope[0] >= end):
            for i in range(self.scope[0], self.scope[1]):
                del self[i]

        elif self.scope[0] <= begin and self.scope[1] <= end:
            for i in range(self.scope[0], begin):
                del self[i]
                    
        elif self.scope[0] >= begin and self.scope[1] >= end:
            for i in range(end, self.scope[1]):
                del self[i]
        else:
            raise IndexError("scope ({lower},{upper}) is not expected".format(lower=begin, upper=end))

        for i in range(begin, end):
            if self.data[i] is None:
                self.load_each(i)

        assert len(self) == self.total, "deletion on mistake"
        self.scope = (begin, end)
        
    def load_each(self, i):
        if self.data[i] is None:
            imageData = read(self.imgPathList[i], None)
            image = QImage.fromData(imageData)
            self.data[i] = image

    def stop(self):
        pass
