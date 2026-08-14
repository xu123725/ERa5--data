"""主窗口：页签、顶部状态栏与启动配置检查。"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStyle, QTabWidget, QVBoxLayout, QWidget

from app.core.config import is_cdsapirc_valid
from app.ui.download_tab import DownloadTab
from app.ui.help_tab import HelpTab
from app.ui.plot_tab import PlotTab
from app.ui.process_tab import ProcessTab
from app.ui.settings_tab import SettingsTab

APP_VERSION = "1.1.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ERA5 数据下载器")
        self.resize(1100, 780)

        self.tabs = QTabWidget()
        self.download_tab = DownloadTab()
        self.process_tab = ProcessTab()
        self.plot_tab = PlotTab()
        self.settings_tab = SettingsTab()
        self.help_tab = HelpTab()
        style = self.style()
        self.tabs.addTab(self.download_tab, style.standardIcon(QStyle.SP_ArrowDown), "下载")
        self.tabs.addTab(self.process_tab, style.standardIcon(QStyle.SP_FileDialogContentsView), "数据处理")
        self.tabs.addTab(self.plot_tab, style.standardIcon(QStyle.SP_FileDialogDetailedView), "绘图")
        self.tabs.addTab(self.settings_tab, style.standardIcon(QStyle.SP_FileDialogInfoView), "设置")
        self.tabs.addTab(self.help_tab, style.standardIcon(QStyle.SP_DialogHelpButton), "帮助")

        # 顶部状态栏：CDS 配置状态 + 版本号
        top_bar = QWidget()
        bar = QHBoxLayout(top_bar)
        bar.setContentsMargins(14, 8, 14, 4)
        self.config_dot = QLabel("●")
        self.config_dot.setStyleSheet("font-size:10px;")
        self.config_text = QLabel("CDS 配置：检查中")
        self.config_text.setStyleSheet("color:#64748B;")
        bar.addWidget(self.config_dot)
        bar.addWidget(self.config_text)
        bar.addStretch(1)
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("color:#94A3B8;")
        bar.addWidget(version_label)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(top_bar)
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.settings_tab.config_saved.connect(self._refresh_config_status)
        self._check_config()

    def _refresh_config_status(self):
        """刷新顶部 CDS 配置状态点（启动时与保存配置后调用）。"""
        if is_cdsapirc_valid():
            self.config_dot.setStyleSheet("font-size:10px; color:#16A34A;")
            self.config_text.setText("CDS 配置：已配置")
            self.config_text.setStyleSheet("color:#16A34A; font-weight:600;")
        else:
            self.config_dot.setStyleSheet("font-size:10px; color:#DC2626;")
            self.config_text.setText("CDS 配置：未配置")
            self.config_text.setStyleSheet("color:#DC2626; font-weight:600;")

    def _check_config(self):
        self._refresh_config_status()
        if not is_cdsapirc_valid():
            QMessageBox.warning(
                self,
                "未配置 API",
                "未检测到有效的 CDS API 配置，请在“设置”页填写访问令牌后保存。",
            )
            self.tabs.setCurrentWidget(self.settings_tab)

    def closeEvent(self, event):
        worker = self.download_tab.worker
        if worker.has_pending():
            ret = QMessageBox.question(
                self,
                "确认退出",
                "仍有下载任务进行中，退出后将停止队列。确定退出吗？",
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            worker.stop()
            if not worker.wait(5000):
                worker.terminate()
                worker.wait()
        event.accept()
