#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from PyQt5.QtCore import QThread, pyqtSignal, QPointF
import pandas as pd
import numpy as np
import os
from math import sqrt
from copy import deepcopy
import pickle

import const
from libs.pascal_voc_io import PascalVocReader
# from libs.lib import distancetopoint, averageRadius
from libs.shapeType import shapeTypes
from libs.statisticReport import reportGenerator
from libs.shape import shapeFactory
from libs.shapeType import shapeTypes
from libs.lib import distancetopoint
from collections import namedtuple, OrderedDict
from functools import reduce

# const.LABEL_DEFAULT_TRACK_START = 'Broken 0'

# const.LABEL_DEFAULT_TRACK = 'Broken'
# const.FILENAME_REPORT = 'report.csv'
# const.FILENAME_TRACK = 'track.csv'
# const.CSV_EXT = '.csv'
const.FILENAME_DIAMETERS = 'diameters.txt'

class easyTrackReport(QThread):
    finished = pyqtSignal(str)

    def __init__(self, imgList, labelhist, scale=1):
        super(easyTrackReport, self).__init__()

        if ((imgList is None) or 
            (isinstance(imgList,(tuple, list)) and len(imgList) == 0)):
            return
        
        self.imgPathList = imgList
        self.labelHist = labelhist
        self.scale = scale

        self.csvfilename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_EASYTRACK)
        print("extract info from csv file: {}".format(self.csvfilename))
        if os.path.isfile(self.csvfilename) is False:
            return None
        assert os.path.isfile(self.csvfilename)

        self.track_df = pd.read_csv(self.csvfilename, encoding='utf-8')
        if self.track_df is None or len(self.track_df) == 0:
            return None

        self.dir = self.track_df.get_value(0,'dir')
        self.subdir = self.track_df.get_value(0,'subdir')
        self.dirPath = os.path.join(self.dir, self.subdir)

        self.shapeFactory = shapeFactory()

    def run(self):

        ShapeObj = namedtuple('ShapeObj', ['i_img', 'label', 'shape'])
        # self.track_df = pd.DataFrame(
        # columns=[
        # 'dir', 'subdir', 'imgfile', 
        # 'index', 'label', 'shapeType',
        # 'points', 'difficult'])
        shape_obj_list = []
        for i, row in self.track_df.iterrows():
            imgfile = row.imgfile
            # index = int(row.index)  # label: Broken 0/1/2/...
            label = row.label
            shapeType = row.shapeType
            points = eval(row.points)
            difficult = bool(row.difficult)
            self.shapeFactory.setType(shapeType)
            shape = self.shapeFactory.getShape()
            shape.points = [QPointF(*xy) for xy in points]
            shape.label = label
            shape.difficult = difficult
            shape.close()

            imgfilepath = os.path.join(self.dirPath, imgfile)
            i_imgfilepath = self.imgPathList.index(imgfilepath)

            shape_obj = ShapeObj(i_imgfilepath, label, shape)

            shape_obj_list.append(shape_obj)

        print("shape_obj_list\n", shape_obj_list)
        shape_obj_dict = groupByList(shape_obj_list)
        print("len(shape_obj_dict)", len(shape_obj_dict))
        print("shape_obj_dict", shape_obj_dict)

        broken_info_dict = dict()
        for _, shape_objs in shape_obj_dict.items():
            n_break = len(shape_objs) - 1
            if n_break <= 1:
                continue
            diameters = tuple(shape_obj.shape.getDiameter() for shape_obj in shape_objs[1:])
            if n_break in broken_info_dict.keys():
                broken_info_dict[n_break].append(diameters)
            else:
                broken_info_dict[n_break] = [diameters]
        
        print(broken_info_dict)
        filename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_DIAMETERS)
        with open(filename, 'wb') as f:
            # f.write((broken_info_dict))
            pickle.dump(broken_info_dict, f)
        print("broken_info_dict stored into ", filename)

        # for key, shape_objs in shape_obj_dict.items():
        with open(filename, "rb") as f:
            from_pickle = pickle.load(f)
        print(from_pickle)

        
        # pickle.dump(shape_obj_dict, file)

        self.finished.emit("test")
        



def groupByList(ls, sep=" "):
    ShapeObj = namedtuple('ShapeObj', ['i_img', 'label', 'shape'])
    ls = [ShapeObj(s.i_img, s.label.lower().strip(), s.shape) for s in ls]
    # ls = list(map(lambda s: ShapeObj(s.i_img, s.label.lower().strip(), s.shape), ls))
    ls.sort(key=lambda s: s.label)
    lists = OrderedDict()
    for shape in ls:
        key = " "
        if " " not in shape.label:
            key = shape.label
            lists[key] = []
        if shape.label.split(sep, 1)[0] in lists.keys():
            lists[shape.label.split(sep, 1)[0]].append(shape)
    return lists