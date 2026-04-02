from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
import sys

from ui.main_window import MainWindow
from utils import resource_path


def main():
    app = QApplication(sys.argv)

    icon_path = resource_path("icon.ico")

    app.setWindowIcon(QIcon(icon_path))

    w = MainWindow()
    w.setWindowIcon(QIcon(icon_path))

    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()