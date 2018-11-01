try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import sys

from libs.lib import newIcon

BB = QDialogButtonBox
UNIT1 = 'px'

class scaleDialog(QDialog):
    def __init__(self):
        super(scaleDialog, self).__init__()
        
        self.unit2 = UNIT1
        self.value1 = self.value2 = 1
        
        self.setWindowTitle('Length Scale Transfiguration')
        self.setWindowModality(Qt.NonModal)
#         self.resize(300, 300)
    
        self.unit1LB = QLabel(UNIT1, self)
        self.lineEdit1 = QLineEdit(self)
        doubleValidator = QDoubleValidator(self)
        self.lineEdit1.setValidator(doubleValidator)
        self.unit1LB.setBuddy(self.lineEdit1)
        
        self.equalSignLB = QLabel('=', self)
        self.unit2CB = QComboBox(self)
        self.unit2CB.addItems((UNIT1,'cm','mm'))

        self.lineEdit2 = QLineEdit(self)
        self.lineEdit2.setValidator(doubleValidator)

        self.buttonBox = bb = BB(BB.Ok | BB.Cancel, Qt.Horizontal, self)
        bb.button(BB.Ok).setIcon(newIcon('done'))
        bb.button(BB.Cancel).setIcon(newIcon('undo'))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)

        mainLayout = QGridLayout(self)
        mainLayout.addWidget(self.unit1LB, 0, 1)
        mainLayout.addWidget(self.lineEdit1, 0, 2, 1, 2)
        mainLayout.addWidget(self.equalSignLB, 1,0)
        mainLayout.addWidget(self.unit2CB, 1, 1)
        mainLayout.addWidget(self.lineEdit2, 1,2,1,2)
        mainLayout.addWidget(bb, 2,1,1,3)
        
        
    def popUp(self):
        self.lineEdit1.setText(str(self.value1))
        self.lineEdit2.setText(str(self.value2))
        self.lineEdit1.setFocus(Qt.PopupFocusReason)
        self.lineEdit1.setSelection(0, len(UNIT1))

        return (self.value2/self.value1, self.unit2) if self.exec_() else (1, UNIT1)

    def validate(self):
        try:
            float(self.lineEdit1.text())
            float(self.lineEdit2.text())

        except ValueError:
            self.accept()

        else:
            v1 = float(self.lineEdit1.text())
            v2 = float(self.lineEdit2.text())
            u2 = self.unit2CB.currentText()
            reasonable = (self.unit2CB.currentText() == UNIT1) and (v2 / v1 - 1) > 1e6
            self.value1, self.value2, self.unit2 = (v1, v2, u2) if reasonable else (self.value1, self.value2, self.unit2)
            self.accept()


