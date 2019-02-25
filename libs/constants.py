import sys
import cv2


class _const:
    class ConstError(TypeError):
        pass
    class ConstCaseError(ConstError):
        pass
    
    def __setattr__(self, name, value):
        if name in self.__dict__.keys():
            raise(self.ConstError, "Can't change const. {}".format(name))
        if not name.isupper():
            raise(self.ConstCaseError, \
                'const name "{}" is not all uppercase'.format(name))
        self.__dict__[name] = value

sys.modules["const"]=_const()

import const

const.SETTING_FILENAME = 'filename'
const.SETTING_RECENT_FILES = 'recentFiles'
const.SETTING_WIN_SIZE = 'window/size'
const.SETTING_WIN_POSE = 'window/position'
const.SETTING_WIN_GEOMETRY = 'window/geometry'
const.SETTING_LINE_COLOR = 'line/color'
const.SETTING_FILL_COLOR = 'fill/color'
const.SETTING_ADVANCE_MODE = 'advanced'
const.SETTING_WIN_STATE = 'window/state'
const.SETTING_SAVE_DIR = 'savedir'
const.SETTING_LAST_OPEN_DIR = 'lastOpenDir'
const.SETTING_AUTO_SAVE = 'autosave'
const.SETTING_SINGLE_CLASS = 'singleclass'
const.SETTING_OBSERVE_WINDOW = 'observeWindow'
const.SETTING_SHOW_PREPROCESS = 'showPreprossedImage'

const.N_NEXT = 5
const.N_PREV = 5
# const.EXT = '.xml'
const.JPG_EXT = '.jpg'
# voc_io
const.XML_EXT = '.xml'
const.TXT_EXT = '.txt'
const.ENCODE_METHOD = 'utf-8'
# cache.py
const.LOAD_WHEN_INIT = 100
const.UPDATE_STEP = 100
const.UPDATE_STEP_LABEL = 100000
const.UPDATE_INTERVAL = 500  # ms

# canvas.py
const.OBS_WIN_X = [150, 950]
const.OBS_WIN_Y = [60, 560]
const.TOLERENCE = 1

# preprocessing.py
const.BACKGROUND_FILENAME = "background.jpg"
const.OMIT_FILENAME = [const.BACKGROUND_FILENAME]
const.PREPROSSESS_BACKGROUND_LENGTH = 500
const.PREPROSSESS_BACKGROUND_BETA = 0.85
const.IMREAD_FORMAT = cv2.IMREAD_GRAYSCALE

# shape.py
# const.DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
# const.DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
# const.DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
# const.DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
# const.DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
# const.DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)

# DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
# DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
# DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
# DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
# DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
# DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)