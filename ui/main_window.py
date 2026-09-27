import os
import re
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QLineEdit, QLabel, QSlider,
    QGridLayout, QScrollArea, QComboBox, QProgressBar, QMessageBox
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
from core.video_merge_worker import (
    MAX_INPUTS,
    VideoMergeWorker,
    is_unc_path,
    local_missing_paths,
    normalize_mp4_output_path,
)



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
        self.current_order_code = None
        self.merge_worker = None

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
        self.file_list.itemChanged.connect(self.update_merge_button_state)

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

        merge_row = QHBoxLayout()
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Tự động", "auto")
        self.layout_combo.addItem("Ngang", "horizontal")
        self.layout_combo.addItem("Dọc", "vertical")
        self.layout_combo.addItem("Lưới 2x2", "grid")
        merge_row.addWidget(QLabel("Bố cục ghép"))
        merge_row.addWidget(self.layout_combo)
        left.addLayout(merge_row)

        self.btn_merge = QPushButton("🎞 Ghép video đã chọn")
        self.btn_merge.clicked.connect(self.merge_checked)
        self.btn_merge.setEnabled(False)
        left.addWidget(self.btn_merge)

        self.merge_status = QLabel("Sẵn sàng")
        self.merge_progress = QProgressBar()
        self.merge_progress.setRange(0, 100)
        self.merge_progress.setValue(0)
        self.btn_cancel_merge = QPushButton("Huỷ ghép")
        self.btn_cancel_merge.clicked.connect(self.cancel_merge)
        self.btn_cancel_merge.setEnabled(False)
        left.addWidget(self.merge_status)
        left.addWidget(self.merge_progress)
        left.addWidget(self.btn_cancel_merge)

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
        self.current_order_code = order
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
        self.update_merge_button_state()

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

        paths = self.get_checked_video_paths()

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

    def get_checked_video_paths(self) -> list[str]:
        paths = []
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return paths

    def update_merge_button_state(self, _item=None) -> None:
        can_merge = (
            self.merge_worker is None
            and bool(self.current_order_code)
            and len(self.get_checked_video_paths()) >= 2
        )
        self.btn_merge.setEnabled(can_merge)

    @staticmethod
    def _safe_order_code(order_code: str | None) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (order_code or "").strip())
        return cleaned.strip("_") or "UNKNOWN_ORDER"

    def merge_checked(self) -> None:
        paths = self.get_checked_video_paths()
        if len(paths) < 2:
            QMessageBox.warning(self, "Ghép video", "Vui lòng chọn ít nhất 2 video để ghép.")
            return
        if len(paths) > MAX_INPUTS:
            QMessageBox.warning(self, "Ghép video", f"Chỉ hỗ trợ ghép tối đa {MAX_INPUTS} video.")
            return

        # MULTIPLAY-VIDEO-MERGE-HARDENING-2B: chi kiem tra nhanh file LOCAL tren UI thread.
        # Duong dan UNC/NAS duoc VideoMergeWorker validate ngoai UI thread.
        missing = local_missing_paths(paths)
        if missing:
            QMessageBox.critical(
                self, "Không thể ghép video",
                "Các file sau không tồn tại hoặc không truy cập được:\n" + "\n".join(missing),
            )
            return

        order_code = self._safe_order_code(self.current_order_code)
        default_name = f"MERGED_{order_code}_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        default_path = os.path.join(self.play_folder or os.getcwd(), default_name)
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu video đã ghép", default_path, "Video MP4 (*.mp4)"
        )
        if not output_path:
            return
        output_path = normalize_mp4_output_path(output_path)

        input_keys = {os.path.normcase(os.path.abspath(path)) for path in paths}
        if os.path.normcase(os.path.abspath(output_path)) in input_keys:
            QMessageBox.critical(self, "Đường dẫn không hợp lệ", "File kết quả không được trùng file nguồn.")
            return
        # Output tren UNC: khong probe tren UI thread (QFileDialog da hoi ghi de).
        if not is_unc_path(output_path) and os.path.exists(output_path):
            answer = QMessageBox.question(
                self, "Xác nhận ghi đè",
                "File kết quả đã tồn tại. Bạn có muốn ghi đè không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.start_merge(paths, output_path)

    def start_merge(self, paths: list[str], output_path: str) -> None:
        layout = str(self.layout_combo.currentData())
        self.merge_worker = VideoMergeWorker(
            paths, output_path, layout, self.current_order_code or "UNKNOWN_ORDER"
        )
        self.merge_worker.progress_changed.connect(self.on_merge_progress)
        self.merge_worker.status_changed.connect(self.merge_status.setText)
        self.merge_worker.completed.connect(self.on_merge_completed)
        self.merge_worker.failed.connect(self.on_merge_failed)
        self.merge_worker.cancelled.connect(self.on_merge_cancelled)
        self.merge_worker.finished.connect(self.on_merge_thread_finished)
        self.merge_progress.setRange(0, 100)
        self.merge_progress.setValue(0)
        self.merge_status.setText("Đang chuẩn bị ghép…")
        self.btn_merge.setEnabled(False)
        self.btn_cancel_merge.setEnabled(True)
        self.merge_worker.start()

    def cancel_merge(self) -> None:
        if self.merge_worker and self.merge_worker.isRunning():
            self.merge_status.setText("Đang huỷ…")
            self.btn_cancel_merge.setEnabled(False)
            self.merge_worker.cancel()

    def on_merge_progress(self, percent: int) -> None:
        if percent < 0:
            self.merge_progress.setRange(0, 0)
            return
        if self.merge_progress.maximum() == 0:
            self.merge_progress.setRange(0, 100)
        self.merge_progress.setValue(percent)

    def on_merge_completed(self, output_path: str) -> None:
        self.merge_progress.setRange(0, 100)
        self.merge_progress.setValue(100)
        self.merge_status.setText("Ghép hoàn tất")
        QMessageBox.information(self, "Ghép hoàn tất", f"Đã lưu video tại:\n{output_path}")

    def on_merge_failed(self, message: str) -> None:
        self.merge_progress.setRange(0, 100)
        self.merge_status.setText("Ghép thất bại")
        QMessageBox.critical(self, "Ghép video thất bại", message)

    def on_merge_cancelled(self) -> None:
        self.merge_progress.setRange(0, 100)
        self.merge_progress.setValue(0)
        self.merge_status.setText("Đã huỷ")

    def on_merge_thread_finished(self) -> None:
        worker = self.merge_worker
        self.merge_worker = None
        self.btn_cancel_merge.setEnabled(False)
        self.update_merge_button_state()
        if worker:
            worker.deleteLater()

    def closeEvent(self, event) -> None:
        if self.merge_worker and self.merge_worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Đang ghép video",
                "Video đang được ghép. Bạn có muốn huỷ tác vụ và đóng ứng dụng không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.merge_worker.cancel()
            self.merge_worker.wait(3000)
        event.accept()

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
