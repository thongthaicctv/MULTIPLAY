import os

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

from core.video_thread import VideoThread
from core.file_copy_thread import FileCopyThread


class PlayerFFmpeg(QWidget):

    def __init__(self):
        super().__init__()

        self.thread = None
        self.path = None
        self.current_sec = 0

        # ===== UI =====
        self.label = QLabel()
        self.label.setStyleSheet("background:black")

        self.btn_full = QPushButton("Fullscreen")
        self.btn_save = QPushButton("Save As")

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.btn_full)
        layout.addWidget(self.btn_save)

        self.setLayout(layout)

        # ===== SIGNAL =====
        self.btn_full.clicked.connect(self.fullscreen)
        self.btn_save.clicked.connect(self.save_as)

    # ======================================
    # PLAY VIDEO
    # ======================================

    def play(self, path):

        self.path = path

        if self.thread:
            self.thread.stop()
            self.thread = None

        self.thread = VideoThread(path)
        self.thread.frame_ready.connect(self.update_frame)
        self.thread.position.connect(self.update_time)

        self.thread.start()

    # ======================================
    # FRAME UPDATE
    # ======================================

    def update_frame(self, frame):

        h, w, ch = frame.shape
        bytes_per_line = ch * w

        qimg = QImage(
            frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_BGR888
        )

        pix = QPixmap.fromImage(qimg)

        self.label.setPixmap(
            pix.scaled(
                self.label.width(),
                self.label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )

    # ======================================
    # TIME SYNC
    # ======================================

    def set_time(self, ms):
        if self.thread:
            self.thread.seek(ms)

    def get_time(self):
        if self.thread:
            return self.thread.current_time
        return 0

    def update_time(self, sec):
        self.current_sec = sec

    # ======================================
    # SAVE FILE (COPY NGUYÊN VIDEO)
    # ======================================

    def save_as(self):

        if not self.path:
            return

        name = os.path.basename(self.path)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Video",
            name,
            "Video (*.mkv *.mp4 *.avi)"
        )

        if not save_path:
            return

        self.copy_thread = FileCopyThread(self.path, save_path)

        self.copy_thread.finished.connect(
            lambda: QMessageBox.information(self, "Done", "Saved OK")
        )

        self.copy_thread.error.connect(
            lambda e: QMessageBox.critical(self, "Error", e)
        )

        self.copy_thread.start()

    # ======================================
    # FULLSCREEN
    # ======================================

    def fullscreen(self):
        self.showFullScreen()

    # ======================================
    # STOP
    # ======================================

    def stop(self):
        if self.thread:
            self.thread.stop()