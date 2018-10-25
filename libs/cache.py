#!/usr/bin/env python
# -*- coding: utf-8 -*-
from math import floor, ceil
from PyQt5.QtGui import QImage
import qimage2ndarray
import numpy as np

def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default

class Cache(object):
    
    def __init__(self, imgList, num = 999):
        # 
        # self.dirname = dirname
        if imgList is None or len(imgList) == 0:
            return None
        self.imgPathList = imgList
        self.total = len(self.imgPathList)
        self.cursor = 0  # according to total imgList
        # self.index = 0  # according to cached image list
        # self.capacity = num
        # self.seg = int(self.capacity / 3)
        # self.scope = [0, self.seg * 2]
        # self.seg_scope = [-1, 2]
        self.data = [None for _ in range(self.total)]
        self.inc = 10
        Cache.LOAD_WHEN_INIT = 10        
        self.upperbound = Cache.LOAD_WHEN_INIT
        self.load(Cache.LOAD_WHEN_INIT)
        # self.background = None
        # self.subtractBackGround = True
        # self.getbackground()


    def __getitem__(self,i):
        return self.data[i]

    def __setitem__(self, i, image):
        self.data[i] = image

    def toggleSubtractBackGround(self):
        self.subtractBackGround = not self.subtractBackGround
        
    # def update(self):
    #     new_seg_scope_lower = floor(self.cursor / self.capacity) - 1
    #     new_seg_scope = [new_seg_scope_lower, new_seg_scope_lower + 3]
    #     new_scope = [max(0, new_seg_scope[0] * self.seg), min(self.total, new_seg_scope[1] * self.seg)]
    #     union = 
            # begin = self.currSegIndex  * self.seg_length \
            #         if self.currSegIndex  * self.seg_length>= 0 \
            #         else 0
            # end =  (self.currSegIndex + 3)  * self.seg_length \
            #         if (self.currSegIndex + 3)  * self.seg_length < self.total \
            #         else self.total
            # for i in range(begin, end):
            #     self.data = []
            #     self.data.append(QImage().load(self.imgPathList[i]))
    #     return 

    def load(self, nth):
        start = self.upperbound
        end = min(self.upperbound + self.inc, self.total) 
        if start >= end:
            return
        for i, imgPath in enumerate(self.imgPathList[start:end], start=start):
            if self.data[i] is not None:
                imageData = read(imgPath, None)
                image = QImage.fromData(imageData)
                self.data[i] = image
        self.upperbound += self.inc

    def get(self, filepath=None, currIndex=None):
        if self.isValid(currIndex):
            img = self.data[self.cursor]
            if img is None:
                self.cursor = currIndex
            return self.data[self.cursor]
        if filepath is not None:
            try:
                index = self.imgPathList.index(filepath)
            except ValueError:
                return None
            else:
                tmp_cursor, self.cursor = self.cursor, index
                img = self.data[self.cursor]
                if img is None:
                    self.cursor = tmp_cursor
                return self.data[self.cursor]
        return None

    def isValid(self, currIndex):
        if currIndex is None:
            return False
        elif 0 <= currIndex < self.total:
            self.cursor = currIndex
            return True
        else:
            return False

    # def qimage2numpyarray(self, imgdata):
    #     height = self.data[0].height()
    #     width  = self.data[0].width()
    #     return (qimage2ndarray.rgb_view(imgdata)).reshape(height, width, 3)

    # def numpyarray2qimage(self, numpyarray):
    #     # height = self.numpyarray.shape[1]
    #     # width  = self.numpyarray.shape[0]
    #     numpyarray = np.transpose(numpyarray, (1,0,2))                                                                                                                                                                              
    #     return QImage(numpyarray.tobytes(), numpyarray.shape[1], numpyarray.shape[0], QImage.Format_RGB888)

    # def getbackground(self, n=1000):
    #     height = self.data[0].height()
    #     width  = self.data[0].width()
    #     bg = np.zeros((height, width, 3))
    #     for i, imgdata in enumerate(self.data):
    #         if i >= n:
    #             break
    #         img = self.qimage2numpyarray(imgdata)
    #         bg = np.add(bg, img)
    #     bg = np.array(bg,dtype=int)
        
        