
import os
import sys
import ctypes
import shutil

def setup_vlc_path():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    possible_paths = [
        os.path.join(base_dir, "bin", "vlc"),
        os.path.join(base_dir, "vlc"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]

    for p in possible_paths:
        dll = os.path.join(p, "libvlc.dll")
        plugins = os.path.join(p, "plugins")

        if os.path.exists(dll) and os.path.isdir(plugins):
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            os.environ["PYTHON_VLC_MODULE_PATH"] = plugins
            os.environ["PYTHON_VLC_LIB_PATH"] = dll

            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(p)

            ctypes.CDLL(dll)
            print("FOUND VLC:", p)
            return p

    raise RuntimeError(
        "Không tìm thấy VLC. Hãy cài VLC hoặc copy VLC vào bin/vlc."
    )

VLC_PATH = setup_vlc_path()

import vlc

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
            "--quiet",
            "--network-caching=150",
            "--file-caching=150",
            "--drop-late-frames",
            "--skip-frames"
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
            "Video (*.mp4 *.mkv *.avi *.mov *.ts)"
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