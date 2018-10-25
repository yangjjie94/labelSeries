#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from lxml import etree
import codecs
from libs.shapeType import shapeTypes

XML_EXT = '.xml'
ENCODE_METHOD = 'utf-8'

class PascalVocWriter:

    def __init__(self, foldername, filename, imgSize, databaseSrc='Unknown', localImgPath=None):
        self.foldername = foldername
        self.filename = filename
        self.databaseSrc = databaseSrc
        self.imgSize = imgSize
        self.shapelist = []
        self.localImgPath = localImgPath
        self.verified = False

    def prettify(self, elem):
        """
            Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf8')
        root = etree.fromstring(rough_string)
        return etree.tostring(root, pretty_print=True, encoding=ENCODE_METHOD).replace("  ".encode(), "\t".encode())
        # minidom does not support UTF-8
        '''reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="\t", encoding=ENCODE_METHOD)'''

    def genXML(self):
        """
            Return XML root
        """
        # Check conditions
        if self.filename is None or \
                self.foldername is None or \
                self.imgSize is None:
            return None

        top = Element('annotation')
        if self.verified:
            top.set('verified', 'yes')

        folder = SubElement(top, 'folder')
        folder.text = self.foldername

        filename = SubElement(top, 'filename')
        filename.text = self.filename

        if self.localImgPath is not None:
            localImgPath = SubElement(top, 'path')
            localImgPath.text = self.localImgPath

        source = SubElement(top, 'source')
        database = SubElement(source, 'database')
        database.text = self.databaseSrc

        size_part = SubElement(top, 'size')
        width = SubElement(size_part, 'width')
        height = SubElement(size_part, 'height')
        depth = SubElement(size_part, 'depth')
        width.text = str(self.imgSize[1])
        height.text = str(self.imgSize[0])
        if len(self.imgSize) == 3:
            depth.text = str(self.imgSize[2])
        else:
            depth.text = '1'

        segmented = SubElement(top, 'segmented')
        segmented.text = '0'
        return top

    def addShape(self, shapeType, label, points, difficult):
        # def convert(shapeType, points):
        #     if shapeType == shapeTypes.
        shape = {'shapeType': shapeType, 
                 'points': points,
                 'label': label,
                 'difficult': difficult}
        self.shapelist.append(shape)

    # def convertPoints2BndBox(points):
    #     xmin = float('inf')
    #     ymin = float('inf')
    #     xmax = float('-inf')
    #     ymax = float('-inf')
    #     for p in points:
    #         x = p[0]
    #         y = p[1]
    #         xmin = min(x, xmin)
    #         ymin = min(y, ymin)
    #         xmax = max(x, xmax)
    #         ymax = max(y, ymax)

    #     # Martin Kersner, 2015/11/12
    #     # 0-valued coordinates of BB caused an error while
    #     # training faster-rcnn object detector.
    #     if xmin < 1:
    #         xmin = 1

    #     if ymin < 1:
    #         ymin = 1

    #     return ((int(xmin), int(ymin)), (int(xmax), int(ymax)))

    # def addBndBox(self, xmin, ymin, xmax, ymax, name, difficult):
    #     bndbox = {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}
    #     bndbox['name'] = name
    #     bndbox['difficult'] = difficult
    #     self.shapelist.append(bndbox)

    # def addLine(self.x1, y1, x2, y2, name, difficult)

    def appendObjects(self, top):
        for each_object in self.shapelist:
            each_shapeType = each_object['shapeType']
            each_points = each_object['points']
            each_label = each_object['label']
            each_difficult = each_object['difficult']

            object_item = SubElement(top, 'object')
            shapeType_subitem = SubElement(object_item, 'shapeType')
            shapeType_subitem.text = str(each_shapeType)
            label_subitem = SubElement(object_item, 'label')
            try:
                label_subitem.text = unicode(each_object['label'])
            except NameError:
                # Py3: NameError: name 'unicode' is not defined
                label_subitem.text = each_object['label']
                
            pose = SubElement(object_item, 'pose')
            pose.text = "Unspecified"

            difficult = SubElement(object_item, 'difficult')
            difficult.text = str( bool(each_object['difficult']) & 1 )

            truncated = SubElement(object_item, 'truncated')
            xmin = ymin = float('inf')
            xmax = ymax = float('-inf')

            points_subitem = SubElement(object_item,"points")
            for i, pt in enumerate(each_points):
                point_subsubitem = SubElement(points_subitem, "point")
                X = SubElement(point_subsubitem,"X")
                X.text = str(pt[0])
                Y = SubElement(point_subsubitem,"Y")
                Y.text = str(pt[1])

                xmin = pt[0] if pt[0] < xmin else xmin
                ymin = pt[1] if pt[1] < ymin else ymin
                xmax = pt[0] if pt[0] > xmax else xmax
                ymax = pt[1] if pt[1] > ymax else ymax

            if (int(ymax) >= int(self.imgSize[0])) or (int(ymin) <= 1):
                truncated.text = "1" # max == height or min
            elif (int(xmax) >= int(self.imgSize[1])) or (int(xmin) <= 1):
                truncated.text = "1" # max == width or min
            else:
                truncated.text = "0"

    def save(self, targetFile=None):
        root = self.genXML()
        self.appendObjects(root)
        out_file = None
        if targetFile is None:
            out_file = codecs.open(
                self.filename + XML_EXT, 'w', encoding=ENCODE_METHOD)
        else:
            out_file = codecs.open(targetFile, 'w', encoding=ENCODE_METHOD)

        prettifyResult = self.prettify(root)
        out_file.write(prettifyResult.decode('utf8'))
        out_file.close()


class PascalVocReader:

    def __init__(self, filepath):
        # shapes type:
        # [shapeType, label, 
        #  [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], 
        #  color, color, 
        #  difficult]
        self.shapes = []
        self.filepath = filepath

        self.verified = False
        try:
            self.parseXML()
        except:
            pass

    def getShapes(self):
        return self.shapes

    def addShape(self, shapeType, label, points, difficult):
        # xmin = int(bndbox.find('xmin').text)
        # ymin = int(bndbox.find('ymin').text)
        # xmax = int(bndbox.find('xmax').text)
        # ymax = int(bndbox.find('ymax').text)
        # points = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        self.shapes.append((shapeType, label, points, None, None, difficult))

    def parseXML(self):
        assert self.filepath.endswith(XML_EXT), "Unsupport file format"
        parser = etree.XMLParser(encoding=ENCODE_METHOD)
        xmltree = ElementTree.parse(self.filepath, parser=parser).getroot()
        filename = xmltree.find('filename').text
        try:
            verified = xmltree.attrib['verified']
            if verified == 'yes':
                self.verified = True
        except KeyError:
            self.verified = False

        for object_iter in xmltree.findall('object'):
            shapeType = object_iter.find("shapeType").text
            points_item = object_iter.find("points")
            points = [(int(float(point[0].text)), int(float(point[1].text))) for point in points_item]

            label = object_iter.find('label').text
            # Add chris
            difficult = False
            if object_iter.find('difficult') is not None:
                difficult = bool(int(object_iter.find('difficult').text))
            self.addShape(shapeType, label, points, difficult)
        return True