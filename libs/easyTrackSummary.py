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
import openpyxl

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
from libs.ustr import ustr

const.FILENAME_BROKEN_SUMMARY = 'broken_summary.xlsx'

class easyTrackSummary(QThread):
    finished = pyqtSignal(str)

    def __init__(self, imgList):
        super(easyTrackSummary, self).__init__()

        if ((imgList is None) or 
            (isinstance(imgList,(tuple, list)) and len(imgList) == 0)):
            return

        self.imgFileList = imgList

    def run(self):
        upper_folder = os.path.dirname(os.path.dirname(self.imgFileList[0]))
        info_dict = dict()
        # for folder in os.path.
        for root, dirs, files in os.walk(upper_folder):
            for filename in files:
                if filename.lower().endswith(const.FILENAME_DIAMETERS):
                    relativePath = os.path.join(root, filename)
                    path = ustr(os.path.abspath(relativePath))
                    with open(path, "rb") as f:
                        sub_info_dict = pickle.load(f)
                    for key, value in sub_info_dict.items():
                        if key in info_dict.keys():
                            info_dict[key].extend(value)
                        else:
                            info_dict[key] = value

                    print("sub_info_dict", sub_info_dict)
        print("info_dict", info_dict)

        def genSheetname(s):
            return "broken {}".format(s)

        def genColname(i):
            return "diameter {}".format(i+1)

        df_dict = dict()
        for key, value in info_dict.items():
            columns = [genColname(i) for i in range(key)]  # range(len(value))
            df = pd.DataFrame(value, columns=columns)
            df['diameter of mother drop'] = reduce( lambda x, y: (x**3 + y**3)**(1/3), 
                                                    [df[col] for col in columns])
            columns_frac = [col+" frac" for col in columns]
            for col in columns_frac:
                df[col] = df[col[:-len(" frac")]]**3 / df['diameter of mother drop']**3

            df_dict[key] = df

            print(key)
            print(df)
        
        summary_df_data = []
        for i_df, df in df_dict.items():
            # sheetname = genSheetname(i_df)
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

        filename = os.path.join(upper_folder, const.FILENAME_BROKEN_SUMMARY)
        writer = pd.ExcelWriter(filename)
        for i_df, df in df_dict.items():
            df.to_excel(writer, genSheetname(i_df))
        summary_df.to_excel(writer, "summary")
        writer.save()

        text = ""
        for key,value in info_dict.items():
            text += str(key) + "\n"
            for v in value:
                text += str(v) + "\n"
            text += "\n"

        self.finished.emit(text)



