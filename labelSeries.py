#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import distutils.spawn
import os.path
import platform
import re
import warnings
import webbrowser
import sys
import subprocess
import pandas as pd
import pickle

from functools import partial
from collections import defaultdict

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import resources
# Add internal libs
from libs.constants import *
import const
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText, distancetopoint, averageDiameter
from libs.settings import Settings
from libs.shape import DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.shape import Shape, shapeFactory
from libs.shapeType import shapeTypes
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.yolo_io import YoloReader
from libs.ustr import ustr
from libs.version import __version__
from libs.backendThread import BackendThread
from libs.preprocessing import PreprocessThread
from libs.measureScaleDialog import scaleDialog
from libs.statisticalReport import NumDensityReporter, TrackReporter

__appname__ = 'labelSeires'

# Utility functions and classes.

def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))

def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


# PyQt5: TypeError: unhashable type: 'QListWidgetItem'
class HashableQListWidgetItem(QListWidgetItem):

    def __init__(self, *args):
        super(HashableQListWidgetItem, self).__init__(*args)

    def __hash__(self):
        return hash(id(self))


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Save as Pascal voc xml
        self.defaultSaveDir = defaultSaveDir
        self.usingPascalVocFormat = True
        self.usingYoloFormat = False

        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.labelHist = []
        self.defaultLabelHist = []
        self.lastOpenDir = None

        # Jerry added: used when opened a dir
        self.backend_cache = None
        self.currIndex = None   # acompanied by backend always
        self.backend_pre = None

        # Added by Jerry: used when change the scale
        self.lengthValue = 1
        self.lengthUnit = 'px'
        self.scale2otherscale = {self.lengthUnit:self.lengthValue}
        # self.scaleWindow = scaleWindow()
        self.clipboard = QApplication.clipboard()

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self, 
            listItem=self.labelHist)

        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.prevLabelText = ''

        # functions of shape supported
        self.shapeFactory = shapeFactory()
        self.shapeType = shapeTypes.shape

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        self.useDefaultLabelCheckbox = QCheckBox(u'Use default label')
        self.useDefaultLabelCheckbox.setChecked(False)
        self.defaultLabelTextLine = QLineEdit()
        useDefaultLabelQHBoxLayout = QHBoxLayout()
        useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)
        useDefaultLabelContainer = QWidget()
        useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)

        # Create a widget for edit and diffc button
        self.diffcButton = QCheckBox(u'difficult')
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to listLayout
        listLayout.addWidget(self.editButton)
        listLayout.addWidget(self.diffcButton)
        listLayout.addWidget(useDefaultLabelContainer)

        # Create and add a widget for showing current label items
        self.labelList = QListWidget()
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        listLayout.addWidget(self.labelList)

        self.dock = QDockWidget(u'Label List', self)
        self.dock.setObjectName(u'Labels')
        self.dock.setWidget(labelListContainer)

        # Tzutalin 20160906 : Add file list and dock to move faster
        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(u'File List', self)
        self.filedock.setObjectName(u'Files')
        self.filedock.setWidget(fileListContainer)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        # Tzutalin 20160906 : Add file list and dock to move faster
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # Actions
        action = partial(newAction, self)
        quit_ = action('&Quit', self.close,
                      'Ctrl+Q', 'quit', u'Quit application')

        open_ = action('&Open', self.openFile,
                      'Ctrl+O', 'open', u'Open image or label file')

        opendir = action('&Open Dir', self.openDirDialog,
                         'Ctrl+u', 'open', u'Open Dir')

        changeSavedir = action('&Change Save Dir', self.changeSavedirDialog,
                               'Ctrl+r', 'open', u'Change default saved Annotation dir')

        openAnnotation = action('&Open Annotation', self.openAnnotationDialog,
                                'Ctrl+Shift+O', 'open', u'Open Annotation')

        openNextImg = action('&Next Image', self.openNextImg,
                             'd', 'next', u'Open Next')

        openPrevImg = action('&Prev Image', self.openPrevImg,
                             'a', 'prev', u'Open Prev')

        openNextImgWithLabel = action('Next Labeled Image', self.openNextImgWithLabel,
                                        'Alt+d', 'next label', u'Open Next Label')
        
        openPrevImgWithLabel = action('Prev Labeled Image', self.openPrevImgWithLabel,
                                        'Alt+a', 'prev label', u'Open Prev Label')
        
        openNextNImg = action('Next n Image', partial(self.openNextImg, n=const.N_NEXT),
                             'Shift+D', 'next n-th image', u'Open Next N')
        
        openPrevNImg = action('Prev n Image', partial(self.openPrevImg, n=const.N_PREV),
                                        'Shift+A', 'prev n image', u'Open Prev N')

        verify = action('&Verify Image', self.verifyImg,
                        'space', 'verify', u'Verify Image')

        save = action('&Save', self.saveFile,
                      'Ctrl+S', 'save', u'Save labels to file', enabled=False)

        save_format = action('&PascalVOC', self.change_format,
                      'Ctrl+Alt+S', 'format_voc', u'Change save format', enabled=False)

        saveAs = action('&Save As', self.saveFileAs,
                        'Ctrl+Shift+S', 'save-as', u'Save labels to a different file', enabled=False)

        close = action('&Close', self.closeFile, 'Ctrl+W', 'close', u'Close current file')

        resetAll = action('&ResetAll', self.resetAll, None, 'resetall', u'Reset all')

        color1 = action('Box Line Color', self.chooseColor1,
                        'Ctrl+L', 'color_line', u'Choose Box line color')

        createMode = action('Create\nRectBox', self.setCreateMode,
                            'w', 'new', u'Start drawing Boxs', enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        createBox = action('Create\nRectBox', None,
                        'r', 'new', u'Draw a new Box', enabled=False)
        createBox.triggered.connect(lambda: self.createShape(shapeTypes.box))
        
        createLine = action('Create\nLine', None,
                        'q', 'new', u'Draw a new Line', enabled=False)
        createLine.triggered.connect(lambda: self.createShape(shapeTypes.line))
        createPolygon = action('Create\nPolygon', None,
                        'w', 'new', u'Draw a new Polygon', enabled=False)
        createPolygon.triggered.connect(lambda: self.createShape(shapeTypes.polygon))
        createEllipse = action('Create\nEllipse', None,
                        'e', 'new', u'Draw a new Ellipse', enabled=False)
        createEllipse.triggered.connect(lambda: self.createShape(shapeTypes.ellipse))

        delete = action('Delete\nRectBox', self.deleteSelectedShape,
                        'Delete', 'delete', u'Delete', enabled=False)
        copy = action('&Duplicate\nRectBox', self.copySelectedShape,
                      'Ctrl+D', 'copy', u'Create a duplicate of the selected Box',
                      enabled=False)

        advancedMode = action('&Advanced Mode', self.toggleAdvancedMode,
                              'Ctrl+H', 'expert', u'Switch to advanced mode',
                              checkable=True, enabled=False)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+Shift+A', 'hide', u'Hide all Boxs',
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', u'Show all Boxs',
                         enabled=False)

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action('Zoom &In', partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', u'Increase zoom level', enabled=False)
        zoomOut = action('&Zoom Out', partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', u'Decrease zoom level', enabled=False)
        zoomOrg = action('&Original size', partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', u'Zoom to original size', enabled=False)
        fitWindow = action('&Fit Window', self.setFitWindow,
                           'Ctrl+F', 'fit-window', u'Zoom follows window size',
                           checkable=True, enabled=False)
        fitWidth = action('Fit &Width', self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', u'Zoom follows window width',
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action('&Edit Label', self.editLabel,
                      'Ctrl+E', 'edit', u'Modify the label of the selected Box',
                      enabled=False)
        self.editButton.setDefaultAction(edit)

        shapeLineColor = action('Shape &Line Color', self.chshapeLineColor,
                                icon='color_line', tip=u'Change the line color for this specific shape',
                                enabled=False)
        shapeFillColor = action('Shape &Fill Color', self.chshapeFillColor,
                                icon='color', tip=u'Change the fill color for this specific shape',
                                enabled=False)

        measureScale = action('Measure Scale Configuration', self.chMeasureScale,
                                tip=u'Change the unit of length for acurate status info and other data processing evnet')

        fianlReport = action('Generate Report', self.generateReport,
                                tip=u'Generate final report of labels in this dir, and store it as file')

        easyTrackReport = action('Easily Track Report', self.generateEasyTrackReport,
                                tip=u"Generate track report of lables in this dir, and store it as file in a easier way")

        shape2Clipboard = action('copy shape info to clipboard', self.shapeInfo2Clipboard,
                                tip=u"copy shape information into clipboard")

        imgPath2Clipboard = action('copy image address to clipboard', self.imgFilePath2Clipboard,
                                tip=u'copy image address to clipboard')
        
        help_ = action('&Tutorial', self.showTutorialDialog, None, 'help', u'Show demos')
        showInfo = action('&Information', self.showInfoDialog, None, 'help', u'Information')

        labels = self.dock.toggleViewAction()  # new action: display dock or not
        labels.setText('Show/Hide Label Panel')
        labels.setShortcut('Ctrl+Shift+L')

        # Label list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))
        # set popup menu in Label Panel
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Store actions for further handling.
        self.actions = struct(save=save, save_format=save_format, saveAs=saveAs, open=open_, close=close, resetAll = resetAll,
                              lineColor=color1, 
                              create=(createBox, createLine, createPolygon, createEllipse), 
                              delete=delete, edit=edit, copy=copy,
                              createMode=createMode, editMode=editMode, advancedMode=advancedMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  open_, opendir, save, saveAs, close, resetAll, quit_),
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete,
                                        None, color1),
                              beginnerContext=(
                                  createBox, createLine, createPolygon, createEllipse, 
                                  edit, copy, delete, 
                                  shape2Clipboard, imgPath2Clipboard),
                              advancedContext=(createMode, editMode, edit, copy,
                                               delete, shapeLineColor, shapeFillColor),
                              onLoadActive=(
                                  close, createBox, createLine, createPolygon, createEllipse, createMode, editMode),
                              onShapesPresent=(saveAs, hideAll, showAll))

        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            data=self.menu('&Data'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction("Auto Saving", self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(const.SETTING_AUTO_SAVE, False))
        # Sync single class mode from PR#106
        self.singleClassMode = QAction("Single Class Mode", self)
        self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(const.SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add by Jerry
        self.hasObserveWindow = action("Show Observe Window", self.showObserveWindow,
                                icon=None, tip=u'Show grids',
                                enabled=True)
        self.hasObserveWindow.setCheckable(True)
        self.hasObserveWindow.setChecked(settings.get(const.SETTING_OBSERVE_WINDOW, False))
        # Add by Jerry
        self.showPreprocessed = action("Show Preprocessed Image", self.showPreprocessedImg,
                                shortcut="C", tip=u'Show preprocessed image',
                                checkable=True, enabled=False)
        self.showPreprocessed.setChecked(settings.get(const.SETTING_SHOW_PREPROCESS, False))

        addActions(self.menus.file,
                   (open_, opendir, changeSavedir, openAnnotation, self.menus.recentFiles, save, save_format, saveAs, close, resetAll, quit_))
        addActions(self.menus.help, (help_, showInfo))
        addActions(self.menus.view, (
            self.autoSaving,
            self.singleClassMode,
            labels, advancedMode, None,
            hideAll, showAll, None,
            self.hasObserveWindow, None,
            self.showPreprocessed, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth, None,
            openPrevImg, openNextImg,
            openPrevImgWithLabel, openNextImgWithLabel,
            openPrevNImg, openNextNImg))
        addActions(self.menus.data, (
            measureScale, 
            fianlReport,
            easyTrackReport,
            ))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            open_, opendir, changeSavedir, openNextImg, openPrevImg, verify, save, save_format, None, createBox, createLine, createPolygon, createEllipse, copy, delete, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.actions.advanced = (
            open_, opendir, changeSavedir, openNextImg, openPrevImg, save, save_format, None,
            createMode, editMode, None,
            hideAll, showAll)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(const.SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(const.SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(const.SETTING_RECENT_FILES)

        size = settings.get(const.SETTING_WIN_SIZE, QSize(600, 500))
        position = settings.get(const.SETTING_WIN_POSE, QPoint(0, 0))
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(const.SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(const.SETTING_LAST_OPEN_DIR, None))
        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(const.SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(settings.get(const.SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fillColor = QColor(settings.get(const.SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(const.SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, filepath=self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

    ## Support Functions ##
    def set_format(self, save_format):
        if save_format == 'PascalVOC':
            self.actions.save_format.setText("PascalVOC")
            self.actions.save_format.setIcon(newIcon("format_voc"))
            self.usingPascalVocFormat = True
            self.usingYoloFormat = False

        elif save_format == 'YOLO':
            self.actions.save_format.setText("YOLO")
            self.actions.save_format.setIcon(newIcon("format_yolo"))
            self.usingPascalVocFormat = False
            self.usingYoloFormat = True

    def change_format(self):
        if self.usingPascalVocFormat: self.set_format("YOLO")
        elif self.usingYoloFormat: self.set_format("PascalVOC")

    def noShapes(self):
        return not self.itemsToShapes

    def toggleAdvancedMode(self, value=True):
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        self.editButton.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def populateModeActions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        # self.actions.create is a tuple
        actions = self.actions.create if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        for item in self.actions.create:
            item.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.labelList.clear()
        self.filePath = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == 'Windows':
            return ['C:\\Program Files\\Internet Explorer\\iexplore.exe']
        elif osName == 'Linux':
            return ['xdg-open']
        elif osName == 'Darwin':
            return ['open', '-a', 'Safari']

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createShape(self, shapeType):
        assert self.beginner()
        # if shapeType == shapeTypes:
        self.canvas.setEditing(False)
        for item in self.actions.create:
            item.setEnabled(False)

        self.canvas.shapeFactory.setType(shapeType)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            for item in self.actions.create:
                item.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self):
        if not self.canvas.editing():
            return
        item = self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generateColorByText(text))
            self.setDirty()

    # Tzutalin 20160906 : Add file list and dock to move faster
    def fileitemDoubleClicked(self, item=None):
        if self.backend_cache is None:  # if open single file instead of open a folder
            return
        currIndex = self.getCurrIndexfromFilename(item.text())

        if self.isCurrIndexValid(currIndex, replace=True):
            self.loadFile(currIndex=self.currIndex)

    def getCurrIndexfromFilename(self, filename):
        unicodeFilePath = ustr(filename)
        if unicodeFilePath == self.mImgList[0]:
            return 0
        index = self.mImgList.index(filename)
        return index if index else None

    # Add chris
    def btnstate(self, item= None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return

        item = self.currentItem()
        if not item: # If not selected Item, take the first one
            item = self.labelList.item(self.labelList.count()-1)

        difficult = self.diffcButton.isChecked()

        try:
            shape = self.itemsToShapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.shapesToItems[shape].setSelected(True)
                self.showShapeInfoInStatusBar(shape)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def shapeInfo2Clipboard(self):
        shapeInfo = ""
        if not self._noSelectionSlot:
            shape = self.canvas.selectedShape
            x1, x2 = shape.points[0].x(), shape.points[2].x()
            x1, x2 = (x2, x1) if x2 < x1 else (x1, x2)
            y1, y2 = shape.points[0].y(), shape.points[2].y()
            y1, y2 = (y2, y1) if y2 < y1 else (y1, y2)
            shapeInfo = '(%.1f, %.1f, %.1f, %.1f)' % (x1, y1, x2, y2)
        self.clipboard.setText(shapeInfo)

    def imgFilePath2Clipboard(self):
        if self.currIndex is not None:
            filePath = self.mImgList[self.currIndex]
        else:
            filePath =  ''
        self.clipboard.setText(filePath)

    def showShapeInfoInStatusBar(self, shape):
        message = ''
        if shape.shapeType == shapeTypes.line:
            length = distancetopoint(shape.points[0], shape.points[1]) * self.lengthValue
            message = 'length: %.2f' % length
            message += str(self.lengthUnit)
        elif shape.shapeType == shapeTypes.ellipse:
            diameter = averageDiameter( shape.points[0], shape.points[1],
                                    shape.points[2], shape.points[3]) * self.lengthValue
            message = 'length: %.2f'% diameter
            message += str(self.lengthUnit)
        elif shape.shapeType == shapeTypes.box:
            x1, x2 = shape.points[0].x(), shape.points[2].x()
            x1, x2 = (x2, x1) if x2 < x1 else (x1, x2)
            y1, y2 = shape.points[0].y(), shape.points[2].y()
            y1, y2 = (y2, y1) if y2 < y1 else (y1, y2)
            message = '(%.1f, %.1f, %.1f, %.1f)' % (x1, y1, x2, y2)
        self.status(message)

    def addLabel(self, shape):
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            print('rm empty label')
            return
        item = self.shapesToItems[shape]
        self.labelList.takeItem(self.labelList.row(item))
        del self.shapesToItems[shape]
        del self.itemsToShapes[item]

    def loadLabels(self, shapes):
        s = []
        shapeFac = shapeFactory()
        for shapeType, label, points, line_color, fill_color, difficult in shapes:

            shapeFac.setType(shapeType)
            shape = shapeFac.getShape()
            shape.label = label
            for x, y in points:
                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)

            self.addLabel(shape)

            # update the labels cache
            if self.backend_cache is not None:  # self.cache and self.currIndex is always interlinked
                self.backend_cache.labels_cache[self.currIndex] = s

        self.canvas.loadShapes(s)

    def saveLabels(self, annotationFilePath):
        annotationFilePath = ustr(annotationFilePath)
        if self.labelFile is None:
            self.labelFile = LabelFile()
            self.labelFile.verified = self.canvas.verified

        def format_shape(s):
            return dict(label=s.label,
                        line_color=s.line_color.getRgb(),
                        fill_color=s.fill_color.getRgb(),
                        points=[(p.x(), p.y()) for p in s.points],
                        # add chris
                        difficult = s.difficult,
                        # add Jerry
                        shapeType=s.shapeType)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]

        self.updateLabelsList(annotationFilePath, self.canvas.shapes)

        # Can add differrent annotation formats here
        try:
            if self.usingPascalVocFormat is True:
                if not annotationFilePath.endswith(const.XML_EXT):
                    annotationFilePath += const.XML_EXT
                print ('Img: ' + self.filePath + ' -> Its xml: ' + annotationFilePath)
                self.labelFile.savePascalVocFormat(annotationFilePath, shapes, self.filePath, self.imageData,
                                                   self.lineColor.getRgb(), self.fillColor.getRgb())
            elif self.usingYoloFormat is True:
                annotationFilePath += const.TXT_EXT
                print ('Img: ' + self.filePath + ' -> Its txt: ' + annotationFilePath)
                self.labelFile.saveYoloFormat(annotationFilePath, shapes, self.filePath, self.imageData, self.labelHist,
                                                   self.lineColor.getRgb(), self.fillColor.getRgb())
            else:
                # self.labelFile.save(annotationFilePath, shapes, self.filePath, self.imageData,
                #                     self.lineColor.getRgb(), self.fillColor.getRgb())
                pass
            return True
        except LabelFileError as e:
            self.errorMessage(u'Error saving label data', u'<b>%s</b>' % e)
            return False

    def updateLabelsList(self, annotationFilePath, shapes):
        if self.backend_cache is None:
            return    
        # index = self.mImgList.index(annotationFilePath + const.JPG_EXT)
        self.backend_cache.labels_cache[self.currIndex] = shapes

    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            shape = self.itemsToShapes[item]
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.useDefaultLabelCheckbox.isChecked() or not self.defaultLabelTextLine.text():
            if len(self.labelHist) > 0:
                self.labelDialog = LabelDialog(
                    parent=self, listItem=self.labelHist)

            # Sync single class mode from PR#106
            if self.singleClassMode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.labelDialog.popUp(text=self.prevLabelText)
                self.lastLabel = text
        else:
            text = self.defaultLabelTextLine.text()

        # Add Chris
        self.diffcButton.setChecked(False)
        if text is not None:
            self.prevLabelText = text
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                for item in self.actions.create:
                    item.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if text not in self.labelHist:
                self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def showObserveWindow(self):
        self.canvas.update()
    
    def showPreprocessedImg(self):
        self.loadFile(currIndex=self.currIndex)
        self.canvas.update()

    def enablePreprocessedImg(self):
        self.showPreprocessed.setEnabled(True)

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filePath=None, currIndex=None):
        """Load the specified file, or the last opened file if None."""

        self.resetState()
        self.canvas.setEnabled(False)

        unicodeFilePath = None
        if (filePath is None) and (currIndex is None):
            print("loadFile: invalid params")
            if filePath is None or len(filePath) <= 0:
                return False
            else:
                unicodeFilePath = ustr(filePath)
        if filePath is not None:  # init(), openFile(), openNextImg when open loadRecent
            # load filepath
            unicodeFilePath = ustr(filePath)
            # load image
            if self.updateLabelFile(unicodeFilePath):  # update self.updateLabelFile
                self.imageData = read(unicodeFilePath, None)
                image = QImage.fromData(self.imageData)
                if self.backend_cache:
                    self.backend_cache.cache[self.currIndex] = image
            else:
                print("loadFile: filePath is invalid")
                return False
            # load labels
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes) 

        if currIndex is not None:  # DoubleClicked(replace=True), openPrev(), openNext()
            assert self.backend_cache is not None, "only cache can be called by index"
            # load image and labels
            image, labels = self.backend_cache[self.currIndex]

            # show preprocessed img
            if self.showPreprocessed.isChecked():
                image = self.backend_pre[self.currIndex]

            if labels:
                self.canvas.loadShapes(labels)
            # load filepath
            filePath = self.mImgList[self.currIndex]
            unicodeFilePath = ustr(filePath)
            
        if unicodeFilePath is None or len(unicodeFilePath) == 0:
            return False

        if unicodeFilePath and self.fileListWidget.count() > 0:
            index = self.mImgList.index(unicodeFilePath)
            fileWidgetItem = self.fileListWidget.item(index)
            fileWidgetItem.setSelected(True)

        if image.isNull():
            print(unicodeFilePath)
            self.errorMessage(u'Error opening file',
                                u"<p>Make sure <i>%s</i> is a valid image file." % unicodeFilePath)
            self.status("Error reading %s" % unicodeFilePath)
            return False

        self.status("Loaded %s" % os.path.basename(unicodeFilePath))
        self.image = image
        self.filePath = unicodeFilePath
        self.canvas.loadPixmap(QPixmap.fromImage(image))
                
        self.setClean()
        self.canvas.setEnabled(True)
        self.adjustScale(initial=True)
        self.paintCanvas()
        self.addRecentFile(self.filePath)
        self.toggleActions(True)
        # Label xml file and show bound box according to its filename
        # if self.usingPascalVocFormat is True:
        if self.defaultSaveDir is not None:
            basename = os.path.basename(
                os.path.splitext(self.filePath)[0])
            xmlPath = os.path.join(self.defaultSaveDir, basename + const.XML_EXT)
            txtPath = os.path.join(self.defaultSaveDir, basename + const.TXT_EXT)
            """Annotation file priority:
            PascalXML > YOLO
            """
            if os.path.isfile(xmlPath):
                self.loadPascalXMLByFilename(xmlPath)
            elif os.path.isfile(txtPath):
                self.loadYOLOTXTByFilename(txtPath)
        else:
            xmlPath = os.path.splitext(filePath)[0] + const.XML_EXT
            txtPath = os.path.splitext(filePath)[0] + const.TXT_EXT
            if os.path.isfile(xmlPath):
                self.loadPascalXMLByFilename(xmlPath)
            elif os.path.isfile(txtPath):
                self.loadYOLOTXTByFilename(txtPath)

        self.setWindowTitle(__appname__ + ' ' + filePath)

        # Default : select last item if there is at least one item
        if self.labelList.count():
            self.labelList.setCurrentItem(self.labelList.item(self.labelList.count()-1))
            self.labelList.item(self.labelList.count()-1).setSelected(True)
        self.canvas.setFocus(True)
        return True

    def updateLabelFile(self, filename):
        unicodeFilePath = ustr(filename)
        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                    (u"<p><b>%s</b></p>"
                                    u"<p>Make sure <i>%s</i> is a valid label file.")
                                    % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
            else:
                self.labelFile = None
            return True
        else:
            return False

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[const.SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[const.SETTING_FILENAME] = ''

        settings[const.SETTING_WIN_SIZE] = self.size()
        settings[const.SETTING_WIN_POSE] = self.pos()
        settings[const.SETTING_WIN_STATE] = self.saveState()
        settings[const.SETTING_LINE_COLOR] = self.lineColor
        settings[const.SETTING_FILL_COLOR] = self.fillColor
        settings[const.SETTING_RECENT_FILES] = self.recentFiles
        settings[const.SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[const.SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[const.SETTING_SAVE_DIR] = ""

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[const.SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[const.SETTING_LAST_OPEN_DIR] = ""

        settings[const.SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[const.SETTING_SINGLE_CLASS] = self.singleClassMode.isChecked()
        settings[const.SETTING_OBSERVE_WINDOW] = self.hasObserveWindow.isChecked()
        settings[const.SETTING_SHOW_PREPROCESS] = self.showPreprocessed.isChecked()
        settings.save()
    ## User Dialogs ##

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    # add by Jerry
                    if file in const.OMIT_FILENAME:
                        continue
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images
    
    def scanAllXmls(self):
        def scanAllFiles(folderPath, extensions=['.xml']):
            if folderPath is None:
                QMessageBox.information(self, u'notice', '请先选择数据文件存储文件夹 Save Dir')
                return []
                # QMessageBox.warning(self,'warning','请先选择数据文件存储文件夹 Save Dir',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)
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
        
        xmls = scanAllFiles(self.defaultSaveDir)
        xml2ImgIndices = []
        mImgBasenameList = [os.path.basename(i) for i in self.mImgList]
        for xml in xmls:
            xmlfile = os.path.basename(xml)
            imgfile = xmlfile[:len(xmlfile)-len(const.XML_EXT)] + const.JPG_EXT
            try:
                ind = mImgBasenameList.index(imgfile)
                xml2ImgIndices.append(ind)
            except:
                pass

        return xml2ImgIndices

    def changeSavedirDialog(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                       '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                       | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotationDialog(self, _value=False):
        if self.filePath is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.filePath))\
            if self.filePath else '.'
        if self.usingPascalVocFormat:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self,'%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]

                # add by Jerry
                self.label

            self.loadPascalXMLByFilename(filename)

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return
        print("in openDirDialog")
        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        self.importDirImages(targetDirPath)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.fileListWidget.clear()
        self.mImgList = self.scanAllImages(dirpath)
        self.xml2imgList = self.scanAllXmls()
        for imgPath in self.mImgList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

        self.currIndex = -1
    
        # connect and start after choosing a dirname
        self.backend_cache = BackendThread(self.mImgList)
        self.backend_cache.start()

        self.showPreprocessed.setEnabled(False)
        self.backend_pre = PreprocessThread(self.mImgList)
        self.backend_pre.backgroundGenerated.connect(self.enablePreprocessedImg)
        self.backend_pre.start()

        self.openNextImg()

    def verifyImg(self, _value=False):
        # Proceding next image without dialog if having any label
         if self.filePath is not None and self.labelFile is not None:
            try:
                self.labelFile.toggleVerify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.saveFile()
                self.labelFile.toggleVerify()

            self.canvas.verified = self.labelFile.verified
            self.paintCanvas()
            self.saveFile()

    def isCurrIndexValid(self, currIndex, replace=False):
        if currIndex is None or (self.backend_cache is None):
            return False
        elif isinstance(currIndex, int) and 0 <= currIndex < len(self.mImgList):
            if replace:
                self.currIndex = currIndex
            return True
        else:
            return False

    def openPrevImg(self, _value=False, n=1):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return

        if self.filePath is None:
            return
        
        if self.backend_cache is None:
            if self.filePath is not None:
                self.loadFile(filePath=self.filePath)
            else:
                return
        else:
            if self.isCurrIndexValid(self.currIndex - n, replace=True):  #  self.currIndex already add 1 to itself
                self.loadFile(currIndex =self.currIndex)

    def openNextImg(self, _value=False, n=1):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return

        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return
        # filename = None

        if self.backend_cache is None:  # single pic
            if self.filePath is not None:
                self.loadFile(filePath=self.filePath)
            else:
                return
        else:                           # seires
            if self.isCurrIndexValid(self.currIndex + n, replace=True):  #  self.currIndex already add 1 to itself
                self.loadFile(currIndex=self.currIndex)    
    
    def openNextImgWithLabel(self):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return
        
        if not self.mayContinue():
            return

        if len(self.mImgList) <= 0:
            return
        # filename = None

        if self.backend_cache is None:  # single pic
            if self.filePath is not None:
                self.loadFile(filePath=self.filePath)
            else:
                return
        else:                           # seires
            nextImgIndex = self.currIndex
            for index in self.xml2imgList:
                if index > nextImgIndex:
                    nextImgIndex = index
                    break
            if nextImgIndex == self.currIndex:
                return
            if self.isCurrIndexValid(nextImgIndex, replace=True):
                self.loadFile(currIndex=nextImgIndex)
            
    def openPrevImgWithLabel(self):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.defaultSaveDir is not None:
                if self.dirty is True:
                    self.saveFile()
            else:
                self.changeSavedirDialog()
                return
        if not self.mayContinue():
            return
        if len(self.mImgList) <= 0:
            return
        if self.filePath is None:
            return
        if self.backend_cache is None:  # single pic
            if self.filePath is not None:
                self.loadFile(filePath=self.filePath)
            else:
                return
        else:                           # seires
            nextImgIndex = self.currIndex
            for index in reversed(self.xml2imgList):
                if index < nextImgIndex:
                    nextImgIndex = index
                    break
            if nextImgIndex == self.currIndex:
                return
            if self.isCurrIndexValid(nextImgIndex, replace=True):
                self.loadFile(currIndex=nextImgIndex)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        formats = ['*.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        filters = "Image & Label files (%s)" % ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)
        self.currIndex = None
        del self.backend_cache
        self.backend_cache = None
        self.showPreprocessed.setEnabled(False)

    def saveFile(self, _value=False):
        if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
            if self.filePath:
                imgFileName = os.path.basename(self.filePath)
                savedFileName = os.path.splitext(imgFileName)[0]
                savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
                self._saveFile(savedPath)
        else:
            imgFileDir = os.path.dirname(self.filePath)
            imgFileName = os.path.basename(self.filePath)
            savedFileName = os.path.splitext(imgFileName)[0]
            savedPath = os.path.join(imgFileDir, savedFileName)
            self._saveFile(savedPath if self.labelFile
                           else self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            return dlg.selectedFiles()[0]
        return ''

    def _saveFile(self, annotationFilePath):
        print("annotationFilePath", annotationFilePath)
        if annotationFilePath and self.saveLabels(annotationFilePath):
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
            self.statusBar().show()
        self.xml2imgList = self.scanAllXmls()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabel(self.canvas.deleteSelected())
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                        self.defaultLabelHist = [line]
                    else:
                        self.labelHist.append(line)
                        self.defaultLabelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        self.set_format("PascalVOC")

        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified

    def loadYOLOTXTByFilename(self, txtPath):
        if self.filePath is None:
            return
        if os.path.isfile(txtPath) is False:
            return

        self.set_format("YOLO")
        tYoloParseReader = YoloReader(txtPath, self.image)
        shapes = tYoloParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tYoloParseReader.verified

    # Add by Jerry: following four are related callable functions 
    # to actions in "data" menu
    def chMeasureScale(self):
        self.lengthValue, self.lengthUnit = scaleDialog().popUp()
        self.scale2otherscale.update({self.lengthUnit: self.lengthValue})

    def generateReport(self):
        if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
            print("Annotation Pathway: ", self.defaultSaveDir)
        else:
            print("Please Choose Annotation Dir First: ", self.defaultSaveDir)
            return
        # self.set_format("PascalVOC")  # only consider PascalVOC format
        self.numDensityReport = NumDensityReporter(self.defaultSaveDir, scale=(self.lengthValue, self.lengthUnit))
        self.numDensityReport.finished.connect(partial(QMessageBox.about,self, "Number Density Report Done"))
        self.numDensityReport.start()

    def generateTrackReport(self):
        if self.filePath and os.path.isdir(self.filePath):
            return
        # self.set_format("PascalVOC")  # only consider PascalVOC format
        self.trackReportGen = reportTrack(self.mImgList, scale=self.lengthValue)
        self.trackReportGen.finished.connect(partial(QMessageBox.about,self, "Number Density Report Done"))
        self.trackReportGen.start()

    def generateEasyTrackReport(self):
        if self.filePath and os.path.isdir(self.filePath):
            return
        # self.set_format("PascalVOC")  # only consider PascalVOC format
        self.easyTrackReportGen = TrackReporter(self.defaultSaveDir, scale=(self.lengthValue, self.lengthUnit), labelHist=self.labelHist)
        self.easyTrackReportGen.finished.connect(partial(QMessageBox.about,self, "Broken Frequency of Droplet Report Done"))
        self.easyTrackReportGen.start()


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else os.path.join(
                         os.path.dirname(sys.argv[0]),
                         'data', 'predefined_classes.txt'),
                     argv[3] if len(argv) >= 4 else None)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
