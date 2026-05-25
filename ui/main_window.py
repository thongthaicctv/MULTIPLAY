import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QLineEdit, QLabel, QSlider,
    QGridLayout, QScrollArea
)

from PyQt6.QtCore import Qt


from core.sync_manager import SyncManager
from core.config_manager import ConfigManager
from core.indexer import Indexer

from ui.player_vlc_widget import PlayerVLC

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from utils import resource_path
# thêm shadow
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor

from core.database_reader import DatabaseReader



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ATG MULTIPLAY V8.8 (phần mềm xem nhiều video cùng lúc cho ATG Recorder - hotline:  0904143113)")
        self.resize(900, 600)
        
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(resource_path("antn.png")))
        self.logo.setScaledContents(True)
        self.logo.setFixedHeight(80)  # chỉnh kích thước tùy bạn

        self.index = {}
        self.players = []
        self.play_folder = None

        self.sync = SyncManager()
        self.config = ConfigManager()

        self.build_ui()
        self.load_saved_folder()

    # ================= UI =================

    def build_ui(self):

        root = QHBoxLayout()

        # ===== LEFT PANEL =====
        left = QVBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã đơn hàng...")
        self.search.textChanged.connect(self.filter_order)



        self.order_list = QListWidget()
        self.order_list.itemClicked.connect(self.load_files)

        self.file_list = QListWidget()

        self.btn_play = QPushButton("▶ Phát các video đã chọn")
        self.btn_play.clicked.connect(self.play_checked)
        self.btn_play.setStyleSheet("""
            QPushButton {
                border: 2px solid #28a745;
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #218838;
                border: 2px solid #1e7e34;
            }
            QPushButton:pressed {
                background-color: #1c7430;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(40, 167, 69))
        shadow.setOffset(0)

        self.btn_play.setGraphicsEffect(shadow)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timeline)
        self.timer.start(500)

        self.db_refresh_timer = QTimer()
        self.db_refresh_timer.timeout.connect(
            lambda: self.load_index_from_database(silent=True)
        )

    

        left.addWidget(self.search)
        
        left.addWidget(QLabel("Danh sách mã đơn hàng"))
        left.addWidget(self.order_list)
        left.addWidget(QLabel("Chọn video để phát"))
        left.addWidget(self.file_list)
        left.addWidget(self.btn_play)

        # ===== RIGHT PANEL =====
        self.grid = QGridLayout()

        video_widget = QWidget()
        video_widget.setLayout(self.grid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(video_widget)

        right = QVBoxLayout()
        right.addWidget(scroll)

        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.sliderReleased.connect(self.seek_all)

        self.timeline.setMinimum(0)
        self.timeline.setMaximum(60 * 60 * 1000)  # 60 phút (ms)

        right.addWidget(QLabel("Timeline"))
        right.addWidget(self.timeline)

        root.addLayout(left, 1)
        root.addLayout(right, 4)

        w = QWidget()
        w.setLayout(root)
        self.setCentralWidget(w)
        # hiển thị thư mục được chọn
        self.lbl_folder = QLabel("No folder selected")
        self.lbl_folder.setStyleSheet("color:blue;font-weight:bold")

        left.addWidget(self.lbl_folder)
        
        self.order_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
    # ================= CONFIG =================

    def load_saved_folder(self):

        self.play_folder = self.config.load_folder()

        if not self.play_folder:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Loi Config",
                "Khong tim thay storage_path/play_path hop le trong config.json cua ATG Recorder"
            )
            return

        self.lbl_folder.setText(self.play_folder)

        db_config = self.config.load_database_config()

        if not db_config:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Loi Database",
                "Khong tim thay cau hinh database trong config.json"
            )
            return

        self.load_index_from_database()
        self.db_refresh_timer.start(5000)



    # ================= INDEX =================

    def load_index(self, folder):

        idx = Indexer(folder)
        data = idx.load()

        if not data:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", "Không tìm thấy dữ liệu index. Cần có thư mục index chứa file YYYY-MM-DD.json")
            return

        self.index = data

        self.order_list.clear()

        for k in self.index.keys():
            self.order_list.addItem(str(k))
        
        print(list(self.index.keys())[:20])

    # ================= SEARCH =================

    def filter_order(self, text):

        text = text.strip().lower()

        self.order_list.clear()

        for code in self.index.keys():

            code_str = str(code).lower()

            if text in code_str:
                self.order_list.addItem(str(code))

    # ================= FILE LOAD =================

    def load_files(self, item, checked_paths=None):

        order = item.text()
        checked_paths = checked_paths or set()

        self.file_list.clear()

        for path in self.index.get(order, []):

            it = QListWidgetItem(os.path.basename(path))
            it.setData(Qt.ItemDataRole.UserRole, path)

            if path in checked_paths:
                it.setCheckState(Qt.CheckState.Checked)
            else:
                it.setCheckState(Qt.CheckState.Unchecked)

            self.file_list.addItem(it)

    # ===== PLAY MULTI =====

    def play_checked(self):

        # clear layout cũ
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().stop()
                item.widget().deleteLater()

        self.players.clear()
        self.sync.clear()

        paths = []

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)

            if item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))

        if not paths:
            return

        # ===== auto layout =====
        import math
        cols = math.ceil(math.sqrt(len(paths)))

        r = c = 0

        for path in paths:

            player = PlayerVLC()
            player.play(path)

            self.grid.addWidget(player, r, c)

            self.players.append(player)
            self.sync.add_player(player)

            c += 1
            if c >= cols:
                c = 0
                r += 1
        
        
        def update_length():
            if not self.players:
                return

            length = self.players[0].player.get_length()

            print("VIDEO LENGTH:", length)  # debug

            if length > 0:
                self.timeline.setMaximum(length)

        # 🔥 delay để VLC load xong
        QTimer.singleShot(800, update_length)

    #TẠO HÀM SEEK CHUẨN
    def seek_all(self):

        value = self.timeline.value()
        max_val = self.timeline.maximum()

        if max_val == 0:
            return

        pos = value / max_val

        for p in self.players:
            p.set_position(pos)


    #AUTO UPDATE TIMELINE
    def update_timeline(self):

        if not self.players:
            return

        p = self.players[0]

        pos = p.get_position()  # 0 → 1

        if pos < 0:
            return

        max_val = self.timeline.maximum()

        value = int(pos * max_val)

        self.timeline.blockSignals(True)
        self.timeline.setValue(value)
        self.timeline.blockSignals(False)
        #self.sync.start()

    def load_index_from_database(self, silent=False):

        reader = DatabaseReader(
            self.config.load_database_config(),
            self.play_folder
        )

        data = reader.load_video_index()

        if not data:
            if silent:
                return

            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                "Khong tim thay video trong database MySQL"
            )
            return

        if data == self.index:
            return

        current_order = None
        current_item = self.order_list.currentItem()
        checked_paths = set()

        if current_item:
            current_order = current_item.text()

        for i in range(self.file_list.count()):
            file_item = self.file_list.item(i)

            if file_item.checkState() == Qt.CheckState.Checked:
                checked_paths.add(file_item.data(Qt.ItemDataRole.UserRole))

        self.index = data
        self.filter_order(self.search.text())

        if current_order and current_order in self.index:
            matches = self.order_list.findItems(
                current_order,
                Qt.MatchFlag.MatchExactly
            )

            if matches:
                self.order_list.setCurrentItem(matches[0])
                self.load_files(matches[0], checked_paths)

        print("MYSQL ORDERS:", len(self.index))
