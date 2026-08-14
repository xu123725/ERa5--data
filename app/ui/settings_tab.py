"""设置页：API 密钥管理。"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import (
    DEFAULT_URL,
    is_cdsapirc_valid,
    read_cdsapirc,
    write_cdsapirc,
)


class SettingsTab(QWidget):
    config_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("API 设置")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        self.url_edit = QLineEdit()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        form.addRow("API 地址 (url):", self.url_edit)
        form.addRow("访问令牌 (key):", self.key_edit)
        layout.addLayout(form)

        self.save_btn = QPushButton("保存并写入配置文件")
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

        tip = QLabel(
            "配置文件位置：%USERPROFILE%\\.cdsapirc\n\n"
            "下载前需先在 CDS 网页（cds.climate.copernicus.eu）登录并同意所下载数据集的使用条款；"
            "否则请求会返回 403。"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch(1)

    def _set_status(self, text: str, color: str | None = None):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color}; font-weight:600;" if color else "")

    def _refresh_status(self):
        if is_cdsapirc_valid():
            cfg = read_cdsapirc()
            self._set_status(f"当前配置有效：url={cfg['url']}，key={cfg['key'][:8]}…", "#16A34A")
            self.url_edit.setText(cfg["url"])
            self.key_edit.setText(cfg["key"])
        else:
            self._set_status("未检测到有效配置，请填写 API 地址与访问令牌后保存。", "#D97706")
            self.url_edit.setText(DEFAULT_URL)
            self.key_edit.setText("")

    def _save(self):
        url = self.url_edit.text().strip()
        key = self.key_edit.text().strip()
        if not url or not key:
            QMessageBox.warning(self, "提示", "请填写完整的 API 地址和访问令牌。")
            return
        try:
            write_cdsapirc(url, key)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self._refresh_status()
        self.config_saved.emit()
        QMessageBox.information(self, "成功", "配置已保存到 ~/.cdsapirc。")
