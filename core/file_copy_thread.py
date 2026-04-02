import shutil
from PyQt6.QtCore import QThread, pyqtSignal


class FileCopyThread(QThread):

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src, dst):
        super().__init__()
        self.src = src
        self.dst = dst

    def run(self):
        try:
            shutil.copy2(self.src, self.dst)
            self.finished.emit(self.dst)
        except Exception as e:
            self.error.emit(str(e))