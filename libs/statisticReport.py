#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from PyQt5.QtCore import QThread, pyqtSignal
import pandas as pd
import numpy as np
import os
from math import sqrt

import const
from libs.pascal_voc_io import PascalVocReader
# from libs.lib import distancetopoint, averageRadius
from libs.shapeType import shapeTypes
const.LABEL_DEFAULT_TRACK = 'Broken'
const.FILENAME_REPORT = 'report.csv'
const.FILENAME_TRACK = 'track.csv'
const.FILENAME_EASYTRACK = 'easytrack.csv'
const.CSV_EXT = '.csv'

class reportGenerator(QThread):
    finished = pyqtSignal(str)

    def __init__(self, imgList, labelhist, scale=1):
        super(reportGenerator, self).__init__()
        if ((imgList is None) or 
            (isinstance(imgList,(tuple, list)) and len(imgList) == 0)):
            return
        if ((labelhist is None) or 
            (isinstance(labelhist,(tuple, list)) and len(labelhist) == 0)):
            return
        self.imgPathList = imgList
        self.labelHist = labelhist
        self.scale = scale
        self.report_df = pd.DataFrame(columns=['dir','subdir', 'imgfile', 'index', 'diameter'])
        self.track_df = pd.DataFrame(columns=['dir','subdir', 'imgfile', 'index', 'label', 'shapeType','points', 'difficult'])
        self.easy_track_df = pd.DataFrame(columns=['dir','subdir', 'imgfile', 'index', 'label', 'shapeType','points', 'difficult'])

        print("self.labelHist", self.labelHist)

    def run(self):

        dir_ = os.path.dirname(os.path.dirname(self.imgPathList[0]))
        subdir = os.path.basename(os.path.dirname(self.imgPathList[0]))

        for i_img, imgPath in enumerate(self.imgPathList):
            imgfilename = os.path.basename(imgPath)
            xmlPath = imgPath[:-len(const.JPG_EXT)] + const.XML_EXT
            xmlfilename = os.path.basename(xmlPath)
            if os.path.isfile(xmlPath) is False:
                continue
            tVocParseReader = PascalVocReader(xmlPath)
            shapes = tVocParseReader.getShapes()
            i_label = 0
            i_track = 0
            i_easytrack = 0
            for shape in shapes:
                shapeType, label, points, _, _, difficult = shape
                if shapeType == shapeTypes.ellipse:
                    diameter = getDiameter(points) * self.scale
                    self.report_df = self.report_df.append([{
                        'dir':dir_,
                        'subdir':subdir, 
                        'imgfile':imgfilename, 
                        'index':i_label, 
                        'diameter':diameter}])
                    i_label += 1
                if label.startswith(const.LABEL_DEFAULT_TRACK):
                    try:
                        i_track = int(label[len(const.LABEL_DEFAULT_TRACK)+1:])  # "+1" allows a _ or space
                    except ValueError:
                        i_track = None
                    else:
                        self.track_df = self.track_df.append([{
                            'dir':dir_,
                            'subdir':subdir, 
                            'imgfile':imgfilename, 
                            'index':i_track, 
                            'label':label,
                            'shapeType':shapeType,
                            'points':points,
                            'difficult':difficult}])
                print(label)
                print(label in self.labelHist)
                if not (label in self.labelHist):
                    self.easy_track_df = self.easy_track_df.append([{
                            'dir':dir_,
                            'subdir':subdir, 
                            'imgfile':imgfilename, 
                            'index':i_track, 
                            'label':label,
                            'shapeType':shapeType,
                            'points':points,
                            'difficult':difficult}])
                    i_easytrack += 1

        reportfilename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_REPORT)
        trackfilename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_TRACK)
        easytrackfilename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_EASYTRACK)
        self.report_df.to_csv(reportfilename, index=False, encoding='utf-8')
        self.track_df.to_csv(trackfilename, index=False, encoding='utf-8')
        self.easy_track_df.to_csv(easytrackfilename, index=False, encoding='utf-8')
        
        print(self.easy_track_df)

        text = self.getText()
        self.finished.emit(text)

    def getText(self):

        distribution = ''
        values, bins = np.histogram(self.report_df['diameter'], bins=10, range=None, normed=False)
        bins = [(bins[i], bins[i+1]) for i in range(len(bins)-1)]
        for bin_, value in zip(bins, values):
            distribution += '({0[0]:.2f}, {0[0]:.2f}) : {1: d}\n'.format(bin_, value)
        mean=self.report_df['diameter'].mean()
        text = """
report


total number: {len}
        
distribution:
{distribution}

mean: {mean}


        """.format( len=len(self.report_df),
                    distribution=distribution,
                    mean=mean)
        
        return text

def getDiameter(pts):
    def distance(p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        return sqrt( (x2-x1)**2 + (y2-y1)**2 )
    p1, p2, p3, p4 = pts
    return sqrt(distance(p1, p2) * distance(p3, p4))
    