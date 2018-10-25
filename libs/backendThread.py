from PyQt5.QtCore import QThread, pyqtSignal
import time

class BackendThread(QThread):
    
    update_cache = pyqtSignal(int)   # update cache n: nth times
    update_bgsub = pyqtSignal(bool)  # bgsub finished or not
    
    def __init__(self):
        super(BackendThread, self).__init__()
        self.i = 0
        self._stop = False

    def run(self):
        while True:
            if not self._stop:
                break
            self.update_cache.emit(self.i)
            self.i += 1
            time.sleep(1)

    def stop(self):
        self._stop = True

