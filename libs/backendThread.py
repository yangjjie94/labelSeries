#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2018 Tzutalin
# Create by Jerry Yang <yangjjie94@gmail.com>

from PyQt5.QtCore import QThread, pyqtSignal
import time
from libs.cache import Cache
from libs.labelsCache import LabelsCache

class BackendThread(QThread):
    
    def __init__(self, imgList):
        super(BackendThread, self).__init__()
        if imgList is None or len(imgList) == 0:
            return None
        self.imgPathList = imgList
        self.cache = Cache(self.imgPathList)
        self.labels_cache = LabelsCache(self.imgPathList)
        self.i = 0
        self._stop = False

    def __len__(self):
        return len(self.cache)

    def __getitem__(self,i):
        return (self.cache[i], self.labels_cache[i])

    def get(self, filepath=None, currIndex=None):
        if filepath is not None:
            try:
                index = self.imgPathList.index(filepath)
            except ValueError:
                return None
            else:
                return (self.cache[index], self.labels_cache[index])
        elif currIndex is not None:
            return (self.cache[currIndex], self.labels_cache[index])
        else:
            return None

    def run(self):
        self.cache.start()
        self.labels_cache.start()


    def stop(self):
        self.cache.stop()
        self.labels_cache.stop()
