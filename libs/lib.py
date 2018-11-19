from math import sqrt
from libs.ustr import ustr
import hashlib
import numpy as np
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *


def newIcon(icon):
    return QIcon(':/' + icon)


def newButton(text, icon=None, slot=None):
    b = QPushButton(text)
    if icon is not None:
        b.setIcon(newIcon(icon))
    if slot is not None:
        b.clicked.connect(slot)
    return b


def newAction(parent, text, slot=None, shortcut=None, icon=None,
              tip=None, checkable=False, enabled=True):
    """Create a new action and assign callbacks, shortcuts, etc."""
    a = QAction(text, parent)
    if icon is not None:
        a.setIcon(newIcon(icon))
    if shortcut is not None:
        if isinstance(shortcut, (list, tuple)):
            a.setShortcuts(shortcut)
        else:
            a.setShortcut(shortcut)
    if tip is not None:
        a.setToolTip(tip)
        a.setStatusTip(tip)
    if slot is not None:
        a.triggered.connect(slot)
    if checkable:
        a.setCheckable(True)
    a.setEnabled(enabled)
    return a


def addActions(widget, actions):
    for action in actions:
        if action is None:
            widget.addSeparator()
        elif isinstance(action, QMenu):
            widget.addMenu(action)
        else:
            widget.addAction(action)


def labelValidator():
    return QRegExpValidator(QRegExp(r'^[^ \t].+'), None)


class struct(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def distance(p):
    return sqrt(p.x() * p.x() + p.y() * p.y())

def distancetopoint(p1, p2):
    return sqrt((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2)

def distancetoline(point, line):
    p1, p2 = line
    p1 = np.array([p1.x(), p1.y()])
    p2 = np.array([p2.x(), p2.y()])
    p3 = np.array([point.x(), point.y()])
    if np.dot((p3 - p1), (p2 - p1)) < 0:
        return np.linalg.norm(p3 - p1)
    if np.dot((p3 - p2), (p1 - p2)) < 0:
        return np.linalg.norm(p3 - p2)
    return np.linalg.norm(np.cross(p2 - p1, p1 - p3)) / np.linalg.norm(p2 - p1)

def averageDiameter(p1,p2,p3,p4):
    return sqrt(distancetopoint(p1, p2) * distancetopoint(p3, p4))

def fmtShortcut(text):
    mod, key = text.split('+', 1)
    return '<b>%s</b>+<b>%s</b>' % (mod, key)


def generateColorByText(text):
    s = str(ustr(text))
    hashCode = int(hashlib.sha256(s.encode('utf-8')).hexdigest(), 16)
    r = int((hashCode / 255) % 255)
    g = int((hashCode / 65025)  % 255)
    b = int((hashCode / 16581375)  % 255)
    return QColor(r, g, b, 100)
