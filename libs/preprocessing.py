#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

import os
import cv2
import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtCore import pyqtSignal, QPointF, QThread
import const
from PyQt5.QtGui import QImage

def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default

class PreprocessThread(QThread):
    """background subtraction and other preprossing procedure"""
    backgroundGenerated = pyqtSignal()

    def __init__(self, imgList, length=const.PREPROSSESS_BACKGROUND_LENGTH, imread_format=const.IMREAD_FORMAT):
        super(PreprocessThread, self).__init__()
        self.imgPathList = imgList
        self.backgroundFilePath = os.path.join(os.path.dirname(self.imgPathList[0]), const.BACKGROUND_FILENAME)
        self.background = None
        self.length = length
        self.imread_format = imread_format

    def generateBackground(self):

        tmp_img = cv2.imread(self.imgPathList[0], self.imread_format)    
        background = np.zeros_like(tmp_img, dtype=np.int32)
        for _, f in zip(range(self.length), self.imgPathList):
            img = cv2.imread(f, self.imread_format)
            background = np.add(background, img)
        # print("generateBackground, background", type(background), background.shape)
        # print(self.length, len(self.imgPathList))
        # background /= min(self.length, len(self.imgPathList))
        background = np.divide(background, min(self.length, len(self.imgPathList)))
        cv2.imwrite(self.backgroundFilePath,background)
        return background

    def run(self):
        if os.path.exists(self.backgroundFilePath):
            self.background = cv2.imread(self.backgroundFilePath, self.imread_format)
        if self.background is None:
            self.background = self.generateBackground()
        self.backgroundGenerated.emit()

    def __getitem__(self,i):
        ori = self.load_origin(i)
        result = self.backgroundSubtraction(ori)
        result = self.equalizeHist(result)
        tmp_filepath = os.path.join(os.path.dirname(self.imgPathList[0]), "temp.jpg")
        cv2.imwrite(tmp_filepath, result)
        imageData = read(tmp_filepath, None)
        image = QImage.fromData(imageData)
        os.remove(tmp_filepath)
        return image

    def load_origin(self, i):
        return cv2.imread(self.imgPathList[i], self.imread_format)

    def backgroundSubtraction(self, img, beta=const.PREPROSSESS_BACKGROUND_BETA):
        background = self.background if self.background is not None else self.generateBackground()
        result = np.subtract(img, beta * self.background)
        result = abs(result)

        return result

    def equalizeHist(self, img):
        return cv2.equalizeHist(np.array(img, dtype=np.uint8))


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

#     def ndarray2qimage(ndarray):
# #     qimage = QImage()
#     if len(ndarray.shape) == 2:
#         height, width = ndarray.shape
#     elif len(ndarray.shape) == 3:
#         height, width, depth = ndarray.shape
#     if ndarray.dtype == np.uint8:
#         bytesPerComponent = 8
#         bytesPerLine = bytesPerComponent * width
# #     image = cv2.cvtColor(ndarray, cv2.COLOR_GRAY2RGB) 
#     qimage = QImage(ndarray.data, width, height, bytesPerLine, QImage.Format_RGB888) 
#     return qimage