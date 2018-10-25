import os
import glob
import cv2
import matplotlib.pyplot as plt
from PyQt5.QtCore import pyqtSignal
import numpy as np

# background subtraction and other preprossing procedure
FILENAME = "background.jpg"

class Preprocess:
    preprocessed = pyqtSignal()

    def __init__(self, dirname, length=10):
        if os.path.isdir(dirname):
            self.dirname = dirname
        else:
            return None
        self.imgPathList = glob.glob(os.path.join(self.dirname,'*.jpg'))
        tmp_img = cv2.imread(self.imgPathList[0])
        height, width, depth = tmp_img
        self.bg = np.zeros((height, width, depth))
        self.imgList = []
        self.length = length

    def __call__(self):
        img_path = os.path.join(self.dirname, FILENAME)
        # if we process it before and there exists backgrounnd image.
        if os.path.exists(img_path):
            self.bg = cv2.imread(img_path)
        else:
            for index, f in enumerate(self.imgPathList):
                if index >= self.length:
                    self.bg /= self.length
                    cv2.imwrite(img_path, self.bg)
                    break
                img = cv2.imread(f)
                self.bg = np.add(self.bg, img)
        Preprocess.preprocessed.emit()  # to enable preprocessing action/button in MainWindow
        return self.bg


# plt.imshow(bgimg_gray, cmap='gray')
# ims = []
# cal = []
# cal_gray = []

# image = cv.imread(paths[0])
# bgimg_gray = np.zeros((800, 1072))
# # print(type(bgimg_gray))
# # print(bgimg_gray.shape)
# for index, f in zip(range(len(paths)-1), paths[::step]):
#     if index >= step + 1000:
#         bgimg_gray /= index
#         break
#     image = cv.imread(f)
#     image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
#     image_gray = cv.cvtColor(image, cv.COLOR_RGB2GRAY)

#     bgimg_gray = np.add(bgimg_gray, image_gray)
    
# plt.imshow(bgimg_gray, cmap='gray')