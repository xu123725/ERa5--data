"""ERA5 数据下载器 程序入口。"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def resource_path(relative: str) -> Path:
    """兼容 PyInstaller 打包后的资源路径（_MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base) / relative


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ERA5下载器")
    qss = resource_path("app/resources/style.qss")
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
