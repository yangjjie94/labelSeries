#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from PyQt5.QtCore import QThread, pyqtSignal, QPointF
import pandas as pd
import numpy as np
import os
from math import sqrt
import xlwt
from copy import deepcopy
import pickle
import pprint

import const
from libs.pascal_voc_io import PascalVocReader
# from libs.lib import distancetopoint, averageRadius
from libs.shapeType import shapeTypes
from libs.labelFile import LabelFile, LabelFileError
from libs.shape import Shape, shapeFactory

from libs.lib import distancetopoint
from collections import namedtuple, OrderedDict, defaultdict
from functools import reduce

const.LABEL_DEFAULT_TRACK = 'Broken'
const.FILENAME_CSV = 'report.csv'
const.FILENAME_XLSX = "report.xlsx"
const.FILENAME_TRACK = 'track.csv'
const.FILENAME_EASYTRACK = 'easytrack.csv'
const.CSV_EXT = '.csv'
const.FILENAME_DIAMETERS = "diameters"

class NumDensityReporter(QThread):
    finished = pyqtSignal(str)

    def __init__(self, annotationDir, scale):
        super(NumDensityReporter, self).__init__()
        self.dir = annotationDir
        self.lengthValue, self.lengthUnit = scale
        
    def run(self):
        self.report_df = NumDensityReporter.get_report_df(self.dir, self.lengthValue)
        
        reportfilenamecsv = os.path.join(os.path.dirname(self.dir), const.FILENAME_CSV)
        self.report_df.to_csv(reportfilenamecsv, index=False, encoding='utf-8')

        text = self.getText()
        self.finished.emit(text)

    @staticmethod
    def get_report_df(filesdir, lengthValue):

        filepaths = NumDensityReporter.scanAllFiles(filesdir)

        report_df = pd.DataFrame(columns=['dir','xmlfile', 'index', 'diameter'])
        for i_xml, xmlPath in enumerate(filepaths):
            *dir_, _ = xmlPath.split('_')
            dir_ = os.path.basename("_".join(dir_)) if isinstance(dir_, (list, tuple)) else os.path.basename(dir_)

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
                    diameter = getDiameter(points) * lengthValue
                    report_df = report_df.append([{
                        'dir': dir_,
                        'xmlfile':xmlfilename, 
                        'index':i_label, 
                        'diameter':diameter}])
                    i_label += 1
        return report_df

    def getText(self):

        distribution = ''
        values, bins = np.histogram(self.report_df['diameter'], bins=10, range=None, normed=False)
        bins = [(bins[i], bins[i+1]) for i in range(len(bins)-1)]
        for bin_, value in zip(bins, values):
            distribution += '({0[0]:.2f}, {0[0]:.2f}) : {1: d}\n'.format(bin_, value)
        mean=self.report_df['diameter'].mean()
        text = """
            report


            # video: {lensubdirs}

            # pics: {lenfiles}

            # diameter of droplets: {len}
                    
            distribution:
            {distribution}

            mean: {mean}

            length reported in {lengthUnit} scale
        """.format( len=len(self.report_df),
                    distribution=distribution,
                    mean=mean,
                    lengthUnit=self.lengthUnit,
                    lensubdirs=len(self.report_df['dir'].value_counts()),
                    lenfiles=len(self.report_df['xmlfile'].value_counts()))
        
        return text

    @staticmethod
    def scanAllFiles(folderPath, extensions=['.xml']):
        if not isinstance(extensions, (list, tuple)):
            extensions = [extensions]
        
        filelist = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = os.path.abspath(relativePath)
                    filelist.append(path)
        filelist.sort(key=lambda x: x.lower())
        return filelist


class TrackReporter(QThread):
    finished = pyqtSignal(str)

    def __init__(self, annotationDir, scale, labelHist):
        super(TrackReporter, self).__init__()

        self.dir = annotationDir
        self.lengthValue, self.lengthUnit = scale
        self.labelHist = labelHist

    @staticmethod
    def get_easy_track_report_df(dir, lengthValue, labelHist):
        easy_track_df = pd.DataFrame(columns=['dir', 'xmlfilename', 'index', 'label', 'shapeType','points', 'difficult'])

        filepaths = NumDensityReporter.scanAllFiles(dir)

        for i_xml, xmlPath in enumerate(filepaths):
            *dir_, _ = xmlPath.split('_')
            dir_ = os.path.basename("_".join(dir_)) if isinstance(dir_, (list, tuple)) else os.path.basename(dir_)
            
            xmlfilename = os.path.basename(xmlPath)

            if os.path.isfile(xmlPath) is False:
                continue
            tVocParseReader = PascalVocReader(xmlPath)
            shapes = tVocParseReader.getShapes()
            
            i_easytrack = 0
            for shape in shapes:
                shapeType, label, points, _, _, difficult = shape

                if label not in labelHist:
                    easy_track_df = easy_track_df.append([{
                            'dir':dir_,
                            # 'subdir':subdir, 
                            'xmlfilename':xmlfilename, 
                            'index':i_easytrack, 
                            'label':label,
                            'shapeType':shapeType,
                            'points':points,
                            'difficult':difficult}])
                    i_easytrack += 1
        return easy_track_df

    def run(self):

        xmls = []
        for index, (dirpath, dirnames, filenames) in enumerate(os.walk(self.dir)):
            xmls.extend(list(map(lambda s: os.path.join(dirpath, s), filter(lambda s: True if s.endswith(".xml") else False, filenames))))

        easy_track_df = pd.DataFrame()
        for xml in xmls:
            tVocParseReader = PascalVocReader(xml)
            shapes = tVocParseReader.getShapes()
            
            xmlfilename = os.path.basename(xml)
            *dir_, _ = xml.split('_')
            dir_ = os.path.basename("_".join(dir_)) if isinstance(dir_, (list, tuple)) else os.path.basename(dir_)
            
            i_easytrack = 0
            for shape in shapes:
                shapeType, label, points, _, _, difficult = shape
                if label not in self.labelHist:
                    easy_track_df = easy_track_df.append([{
                            'subdir':dir_,
                            'xmlfilename':xmlfilename, 
                            'index':i_easytrack, 
                            'label':label,
                            'shapeType':shapeType,
                            'points':points,
                            'difficult':difficult}],
                            ignore_index= True)
                    i_easytrack += 1

        easy_track_df.sort_values(by=["subdir", "xmlfilename", "label"]).reindex(range(len(easy_track_df)))


        ShapeObj = namedtuple('ShapeObj', ['subdir', 'label', 'shape'])
        shape_obj_list = []
        shape_obj_dict_list = []

        subdirs = sorted(list(easy_track_df.subdir.value_counts().keys()))

        for i_subdir, subdir in enumerate(subdirs):
            tmp_sub_df = easy_track_df[easy_track_df["subdir"] == subdir].sort_values(by="label")
            shape_obj_list_tmp = []
            
            for i, row in tmp_sub_df.iterrows():
                subdir = row.subdir
                xmlfilename = row.xmlfilename
                shapeType = row.shapeType
                label = row.label.lower().strip()
                points = row.points
                difficult = row.difficult
                shapeFac = shapeFactory()
                shapeFac.setType(shapeType)
                shape = shapeFac.getShape()
                shape.points = [QPointF(*xy) for xy in points]
                shape.label = label
                shape.difficult = difficult
                shape.close()
                
                shape_obj = ShapeObj(subdir, label, shape)
                shape_obj_list_tmp.append(shape_obj)
                
            shape_obj_dict = OrderedDict()
            for shape in shape_obj_list_tmp:
                just_found_one = False
                key = " "
                if " " not in shape.label:
                    key = shape.label
                    shape_obj_dict[key] = []
                    just_found_one = True
                if shape.label.split(" ", 1)[0] in shape_obj_dict.keys():
                    if not just_found_one:
                        shape_obj_dict[shape.label.split(" ", 1)[0]].append(shape)
                    
            # 去除字典中小于1个的情况
            to_del = []
            for key,value in shape_obj_dict.items():
                if len(value) <= 1:
                    to_del.append(key)
            for key in to_del:
                shape_obj_dict.pop(key)
            
            shape_obj_list.extend(shape_obj_list_tmp)
            shape_obj_dict_list.append(shape_obj_dict)

        broken_info_dict = defaultdict(list)
        for shape_obj_dict_tmp in shape_obj_dict_list:
            for _, shape_objs in shape_obj_dict_tmp.items():
                n_break = len(shape_objs)
                diameters = tuple(shape_obj.shape.getDiameter() for shape_obj in shape_objs)
                if n_break in broken_info_dict.keys():
                    broken_info_dict[n_break].append(diameters)
                else:
                    broken_info_dict[n_break] = [diameters]

        def genSheetname(s):
            return "broken {}".format(s)

        def genColname(i):
            return "diameter {}".format(i+1)

        df_dict = dict()
        for key, value in broken_info_dict.items():
            columns = [genColname(i) for i in range(key)]  # range(len(value))
            df = pd.DataFrame(value, columns=columns)
            df['diameter of mother drop'] = reduce( lambda x, y: (x**3 + y**3)**(1/3), 
                                                    [df[col] for col in columns])
            columns_frac = [col+" frac" for col in columns]
            for col in columns_frac:
                df[col] = df[col[:-len(" frac")]]**3 / df['diameter of mother drop']**3

            df_dict[key] = df

        summary_df_data = []
        for i_df, df in df_dict.items():
            columns = [genColname(i) for i in range(i_df)]
            for i, row in df.iterrows():
                drops = list(row[columns])
                assert(len(drops) == i_df)
                drops.sort()
                mother_drops = [0 for _ in range(len(drops))]
                mother_drops[0] = drops[0]
                for i in range(len(drops)-1):
                    drop_1 = mother_drops[i]
                    drop_2 = drops[i+1]
                    mother_drops[i+1] = (drop_1**3 + drop_2**3)**(1/3)
                    drop_1_frac = drop_1**3 / mother_drops[i+1]**3
                    drop_2_frac = drop_2**3 / mother_drops[i+1]**3
                    n_breakage = i_df
                    summary_df_data.append((drop_1, drop_2, mother_drops[i+1], 
                                            drop_1_frac, drop_2_frac, n_breakage))
        summary_df = pd.DataFrame(summary_df_data, columns=[ 'drop_1', 'drop_2', 'mothoer_drop', 
                                            'drop_1_frac', "drop_2_frac", "n_breakage"])

        filename = os.path.join(os.path.dirname(self.dir), "summary-{}.xlsx".format(os.path.basename(self.dir)))
        writer = pd.ExcelWriter(filename)
        for i_df, df in df_dict.items():
            df.to_excel(writer, genSheetname(i_df))
        summary_df.to_excel(writer, "summary")
        writer.save()

        text = "\n".join(["# {i}-elem break: {num}".format(i=str(i).rjust(2), num=str(len(broken_info_dict[i])).rjust(3)) for i in range(2, 11)])
        text += "\n" + "# total: {total}".format(total=len(summary_df))
        self.finished.emit(text)

def getDiameter(pts):
    def distance(p1, p2):
        x1, y1 = p1
        x2, y2 = p2
        return sqrt( (x2-x1)**2 + (y2-y1)**2 )
    p1, p2, p3, p4 = pts
    return sqrt(distance(p1, p2) * distance(p3, p4))
