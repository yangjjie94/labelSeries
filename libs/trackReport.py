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

const.LABEL_DEFAULT_TRACK_START = 'Broken 0'

# const.LABEL_DEFAULT_TRACK = 'Broken'
# const.FILENAME_REPORT = 'report.csv'
# const.FILENAME_TRACK = 'track.csv'
# const.CSV_EXT = '.csv'

class reportTrack(QThread):
    finished = pyqtSignal(str)

    def __init__(self, imgList, scale=1):
        super(reportTrack, self).__init__()
        if ((imgList is None) or 
            (isinstance(imgList,(tuple, list)) and len(imgList) == 0)):
            return
        
        self.imgPathList = imgList
        self.scale = scale

        self.csvfilename = os.path.join(os.path.dirname(self.imgPathList[0]), const.FILENAME_TRACK)
        print("extract info from csv file: {}".format(self.csvfilename))
        if os.path.isfile(self.csvfilename) is False:
            return None
            # reportGenerator(imgList).start()
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
        self.ShapeObjsbyFrame = OrderedDict()
        # self.track_df = pd.DataFrame(
        # columns=[
        # 'dir', 'subdir', 'imgfile', 
        # 'index', 'label', 'shapeType',
        # 'points', 'difficult'])
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
            if i_imgfilepath in self.ShapeObjsbyFrame.keys():
                self.ShapeObjsbyFrame[i_imgfilepath].append(shape_obj)
            else:
                self.ShapeObjsbyFrame[i_imgfilepath] = [shape_obj]

        self.shape_obj_trees = Trees()

        # init self.shape_obj_trees
        for i_img, shape_objs in self.ShapeObjsbyFrame.items():
            for _, shape_obj in enumerate(shape_objs):
                if shape_obj.label == const.LABEL_DEFAULT_TRACK_START:
                    self.shape_obj_trees.append(Tree(shape_obj))
            break

        for i_img, shape_objs in self.ShapeObjsbyFrame.items():
            if i_img+1 in self.ShapeObjsbyFrame.keys():
                next_shape_objs = self.ShapeObjsbyFrame[i_img+1]
                for _, shape_obj in enumerate(shape_objs):
                    tree, node = self.shape_obj_trees.getNode(shape_obj)
                    if tree is not None and node is not None:  # 如果该帧的该图形已经被加到树中，到下一帧去找与它相交的图形，并加为它的孩子
                        for _, next_shape_obj in enumerate(next_shape_objs):
                            if intersects(shape_obj.shape.makePath(), next_shape_obj.shape.makePath()):
                                tree.addKid(node, next_shape_obj)

                    elif shape_obj.label == const.LABEL_DEFAULT_TRACK_START: # 如果该帧的图像暂时不在树中，且满足树根的条件，那么加到树根中去
                        self.shape_obj_trees.append(Tree(shape_obj))
        
        text = self.genText()
        self.finished.emit(text)

    def genText(self):
        paths_dict = self.shape_obj_trees.genPaths()
        n_trees = len(paths_dict)
        TreeStat = namedtuple('TreeStat', ['n_breakage', 'diameters'])
        stat = ""
        tree_stats_dict = OrderedDict()
        for i_tree, paths in paths_dict.items():
            diameters = [0 for _ in range(len(paths))]
            start = paths[0][0].data.i_img
            end = len(paths[0]) + start
            for i_path, path in enumerate(paths):
                end = len(path) + start if len(path) + start > end else end
                n_fork = 0
                for i, node in enumerate(path):
                    for otherpath in paths:
                        if path == otherpath:
                            continue
                        elif i < len(otherpath) and path[i] == otherpath[i]:
                            n_fork = i
                diameters[i_path] = getRadiusFromPath(path[n_fork+1:])
                
            tree_stats_dict[i_tree] = TreeStat( len(paths_dict[i_tree]), diameters)
        for _, tree_stat in tree_stats_dict.items():
            stat += "{n_breakage}-element breakage: from {start} to {end}\n{diameters_}\n".format(
                        n_breakage=tree_stat.n_breakage, 
                        start=start, 
                        end=end, 
                        diameters_="+".join(map(lambda x:"{:.2f}".format(x), tree_stat.diameters)))

        text = """
total breakage #: {}

{}


""".format(n_trees, stat)
        return text

def getRadiusFromPath(path):
    if path is None or len(path) == 0:
        return 0
    for node in path:
        radius, roundity = 0, 0
        if node.data.shape.shapeType == shapeTypes.ellipse:
            p1,p2,p3,p4 = node.data.shape.points
            l1 = distancetopoint(p1,p2)
            l2 = distancetopoint(p3,p4)
            tmp_roundity = l1/l2 if l1/l2 < 1 else l2/l1
            if tmp_roundity > roundity:
                radius, roundity = sqrt(l1*l2), tmp_roundity
    return radius

class Trees():
    def __init__(self):
        self.data = []

    def append(self, tree):
        assert isinstance(tree, Tree)
        self.data.append(tree)
    
    def __len__(self):
        return len(self.data)

    def index(self, tree):
        return self.data.index(tree)

    def __getitem__(self, i):
        return self.data[i]

    def __str__(self):
        return str(self.data)
    
    def __iter__(self):
        return iter(self.data)

    def getNode(self, data):
        for tree in self.data:
            for node in list(tree.members):
                if node.data == data:
                    return tree, node
        return (None, None)

    def genPaths(self):
        paths = OrderedDict()
        for i_tree, tree in enumerate(self.data):
            path = tree.genPaths()
            paths[i_tree] = path
        return paths

    def getAllNodes(self):
        nodes = []
        for tree in self.data:
            nodes.extend(list(tree.members))
        return nodes

    

class Tree(object):
    class TreeError(IndexError):
        pass

    def __init__(self, root):  # root is a shape_obj
        self.root = root if isinstance(root, Node) else Node(root)
        assert(isinstance(self.root, Node))
        self.members = {self.root}
        # self.current = self.root
        
    def addKid(self, node, kid_data):
        assert(isinstance(kid_data, type(self.root.data)))
        kid = Node(kid_data)
        self.update_members(kid)
        node.kids.append(kid)
        kid.parent = node
        kid.i_layer = kid.parent.i_layer+1

    def update_members(self, node):
        if isinstance(node, Node):
            self.members.add(node)
    
    def getNode(self, data):
        if isinstance(data, type(self.root.data)):
            for shape_obj_node in list(self.members):
                if data == shape_obj_node.data:
                    return shape_obj_node
            return None
        else:
            assert(False, "getNode wrong input")

    def __str__(self):
        return "Tree:\n"+ "\n".join([str(m) for m in list(self.members)]) + "\n\n\n"

    def genPaths(self):
        paths = []
        for node in list(self.members):
            if len(node.kids) == 0:
                path = [node]
                while node.parent is not None:
                    path.append(node.parent)
                    node = node.parent
                # i_fork = len(path) - 1
                # while node.parent is not None:
                #     if len(node.parent.kids) == 1:
                #         node.

                paths.append(list(reversed(path)))
            
        return paths
        
    def __in__(self, node):
        return node in self.members

    def __iter__(self):
        return iter(self.root)
    
    def __eq__(self, other):
        return True if self.root == other.root else False

    # def display(self):
    #     '''''树形打印出目录结构'''  
    #     for root, dirs, files in os.walk(startPath):  
    #         #获取当前目录下文件数  
    #         fileCount = fileCntIn(root)  
    #         #获取当前目录相对输入目录的层级关系,整数类型  
    #         level = root.replace(startPath, '').count(os.sep)  
    #         #树形结构显示关键语句  
    #         #根据目录的层级关系，重复显示'| '间隔符，  
    #         #第一层 '| '  
    #         #第二层 '| | '  
    #         #第三层 '| | | '  
    #         #依此类推...  
    #         #在每一层结束时，合并输出 '|____'  
    #         indent = '| ' * 1 * level + '|____'  
    #         print '%s%s -r:%s' % (indent, os.path.split(root)[1], fileCount)  
    #         for file in files:
    #             indent = '| ' * 1 * (level+1) + '|____'  
    #             print '%s%s' % (indent, file) 


class Node(object):
    def __init__(self, data, i_layer=0, parent=None, kids=None, next_=None, prev=None):
        self.parent = parent
        self.kids = [] if kids is None else kids
        self.data = data
        self.i_layer = i_layer

    def __str__(self):
        return "Node: {},\n     parent={},\n     kids={}.\n".format(self.data, self.parent, self.kids)

    def __eq__(self, other):
        return True if self.data == other.data else False

    def __hash__(self):
        return hash(self.data)
        
def intersects(path1, path2):
    return path1.intersects(path2)
        