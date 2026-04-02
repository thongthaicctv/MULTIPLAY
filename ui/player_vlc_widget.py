import vlc
import sys
import os
import shutil

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QMessageBox, QFrame
)


class PlayerVLC(QWidget):

    def __init__(self):
        super().__init__()

        self.video_path = None

        # ===== VLC =====
        self.instance = vlc.Instance(
            "--avcodec-hw=none",
            "--vout=opengl",
            "--quiet"
        )
        self.player = self.instance.media_player_new()

        # ===== UI =====
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background:black")

        self.btn_save = QPushButton("💾 Save")
        self.btn_save.setFixedHeight(30)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        layout.addWidget(self.video_frame)   # 🎬 video
        layout.addWidget(self.btn_save)      # 💾 nút riêng

        self.setLayout(layout)

        # event
        self.btn_save.clicked.connect(self.save_video)

    # ===== PLAY =====
    def play(self, path):

        self.video_path = path

        media = self.instance.media_new(path)
        self.player.set_media(media)

        if sys.platform == "win32":
            self.player.set_hwnd(int(self.video_frame.winId()))
        else:
            self.player.set_xwindow(int(self.video_frame.winId()))

        self.player.play()

    # ===== SAVE =====
    def save_video(self):

        if not self.video_path:
            return

        name = os.path.basename(self.video_path)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Video",
            name,
            "Video (*.mkv)"
        )

        if not save_path:
            return

        try:
            shutil.copy2(self.video_path, save_path)
            QMessageBox.information(self, "Done", "Đã lưu video")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ===== CONTROL =====
    def stop(self):
        self.player.stop()

    def set_time(self, ms):
        self.player.set_time(int(ms))

    def get_time(self):
        return self.player.get_time()
    
    def get_position(self):
        return self.player.get_position()  # 0 → 1


    def set_position(self, pos):
        self.player.set_position(pos)  # 0 → 1