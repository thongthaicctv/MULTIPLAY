from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QPushButton, QTextEdit, QHBoxLayout,
    QFrame, QMessageBox
)

from PyQt6.QtGui import QGuiApplication, QFont
from PyQt6.QtCore import Qt

from core.hardware_id import get_machine_id


class LicenseDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Software Activation")
        self.setFixedSize(520, 320)

        self.machine = get_machine_id()

        layout = QVBoxLayout()

        # ===== TITLE =====
        title = QLabel("⚠ SOFTWARE NOT ACTIVATED")
        title.setStyleSheet("color:red; font-size:18px; font-weight:bold")
        layout.addWidget(title)

        info = QLabel(
            "Please send Machine ID to supplier to activate software."
        )
        layout.addWidget(info)

        # ===== MACHINE ID BOX =====
        self.txt_machine = QTextEdit()
        self.txt_machine.setPlainText(self.machine)
        self.txt_machine.setReadOnly(True)

        self.txt_machine.setStyleSheet("""
            background-color:#222;
            color:#00ff90;
            font-size:14px;
            border:2px solid #00ff90;
        """)

        layout.addWidget(self.txt_machine)

        # ===== CONTACT FRAME =====
        contact_frame = QFrame()
        contact_frame.setStyleSheet("""
            background-color:#fff3cd;
            border:2px solid #ffc107;
            border-radius:6px;
        """)

        contact_layout = QVBoxLayout()

        contact_title = QLabel("📞 CONTACT SUPPORT")
        contact_title.setStyleSheet("font-size:16px; font-weight:bold")

        contact_layout.addWidget(contact_title)

        web = QLabel("🌐 Website: annnguyen.pro - camerathainguyen.com")
        zalo = QLabel("💬 Zalo: 090.414.3113")
        email = QLabel("✉ Email: thongthaictv@gmail.com")

        for w in [web, zalo, email]:
            w.setStyleSheet("font-size:14px; font-weight:bold")
            contact_layout.addWidget(w)

        contact_frame.setLayout(contact_layout)

        layout.addWidget(contact_frame)

        # ===== BUTTONS =====
        btn_layout = QHBoxLayout()

        self.btn_copy = QPushButton("Copy Machine ID")
        self.btn_retry = QPushButton("Retry")
        self.btn_exit = QPushButton("Exit")

        self.btn_copy.setStyleSheet("background:#28a745;color:white;font-weight:bold")
        self.btn_retry.setStyleSheet("background:#007bff;color:white;font-weight:bold")
        self.btn_exit.setStyleSheet("background:#dc3545;color:white;font-weight:bold")

        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_retry)
        btn_layout.addWidget(self.btn_exit)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # ===== SIGNAL =====
        self.btn_copy.clicked.connect(self.copy_id)
        self.btn_retry.clicked.connect(self.accept)
        self.btn_exit.clicked.connect(self.reject)

    def copy_id(self):
        QGuiApplication.clipboard().setText(self.machine)
        QMessageBox.information(self, "Copied", "Machine ID copied!")