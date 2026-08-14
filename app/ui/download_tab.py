"""下载页：模板、请求参数、区域、时间、输出、任务队列与日志。"""

import html
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api.cds_client import DownloadWorker, build_request, normalize_times
from app.core.presets import AREA_PRESETS, DATASET_CATALOG, DATASET_VARIABLES


class DownloadTab(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = DownloadWorker(self)
        self.worker.log_message.connect(self._append_log)
        self.worker.task_status.connect(self._on_task_status)
        self.worker.task_progress.connect(self._on_task_progress)
        self.worker.license_error.connect(self._on_license_error)
        self.worker.start()
        self._docks: list[QDockWidget] = []
        self._build_ui()

    def _make_dock(self, title: str, content: QWidget, min_height: int, area=Qt.TopDockWidgetArea) -> QDockWidget:
        """把功能区包装成可拖动、可悬浮的子窗口。"""
        dock = QDockWidget(title, self)
        dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea
        )
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setWidget(content)
        dock.setMinimumHeight(min_height)
        self.addDockWidget(area, dock)
        self._docks.append(dock)
        return dock

    # ---------- UI 构建 ----------
    def _build_ui(self):
        # 先构建请求参数与时间控件（数据集联动需要引用它们）
        req_widget = QWidget()
        req = QVBoxLayout(req_widget)
        req.setContentsMargins(12, 6, 12, 6)
        hint = QLabel("其余请求参数在此填写（如 product_type、pressure_level、statistic）")
        hint.setWordWrap(True)
        req.addWidget(hint)
        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(["参数名", "参数值"])
        self.params_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.setAlternatingRowColors(True)
        req.addWidget(self.params_table, 1)
        btn_row = QHBoxLayout()
        add_row_btn = QPushButton("添加参数")
        add_row_btn.setToolTip("新增一行参数（参数名/参数值）")
        add_row_btn.setProperty("btnClass", "secondary")
        add_row_btn.clicked.connect(self._add_param_row)
        del_row_btn = QPushButton("删除选中参数")
        del_row_btn.setToolTip("删除选中的参数行")
        del_row_btn.setProperty("btnClass", "ghost")
        del_row_btn.clicked.connect(self._del_param_row)
        btn_row.addWidget(add_row_btn)
        btn_row.addWidget(del_row_btn)
        btn_row.addStretch(1)
        req.addLayout(btn_row)

        time_widget = QWidget()
        time = QHBoxLayout(time_widget)
        time.setContentsMargins(12, 6, 12, 6)
        self.start_date = QDateEdit(QDate.currentDate().addMonths(-1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        # ERA5 再分析数据发布滞后约 5 天，默认结束日期提前到 5 天前，
        # 避免请求超出数据集最新可用日期而失败（可按需手动改回今天）
        self.end_date = QDateEdit(QDate.currentDate().addDays(-5))
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setToolTip("ERA5 再分析数据发布滞后约 5 天，默认已提前；如需最新日期请手动调整")
        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("如 00,06,12,18（留空 = 全部时次）")
        time.addWidget(QLabel("开始:"))
        time.addWidget(self.start_date)
        time.addWidget(QLabel("结束:"))
        time.addWidget(self.end_date)
        time.addWidget(QLabel("时次:"))
        time.addWidget(self.time_edit, 1)

        # 数据集与气象要素（左列）
        sel_widget = QWidget()
        sel = QVBoxLayout(sel_widget)
        sel.setContentsMargins(12, 6, 12, 6)
        ds_row = QHBoxLayout()
        ds_row.addWidget(QLabel("数据集:"))
        self.ds_combo = QComboBox()
        for name in DATASET_CATALOG:
            self.ds_combo.addItem(name)
        self.ds_combo.addItem("自定义…")
        ds_row.addWidget(self.ds_combo, 1)
        sel.addLayout(ds_row)
        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("数据集ID:"))
        self.dataset_edit = QLineEdit()
        self.dataset_edit.setPlaceholderText("CDS 数据集短名（API 参数名）")
        id_row.addWidget(self.dataset_edit, 1)
        sel.addLayout(id_row)
        var_row = QHBoxLayout()
        var_row.addWidget(QLabel("气象要素:"))
        self.var_combo = QComboBox()
        self.var_combo.setEditable(True)
        self.var_combo.setInsertPolicy(QComboBox.NoInsert)
        var_row.addWidget(self.var_combo, 1)
        sel.addLayout(var_row)
        self.ds_combo.currentTextChanged.connect(self._on_dataset_changed)
        self.var_combo.editTextChanged.connect(self._on_variable_changed)

        # 区域（左列）
        area_widget = QWidget()
        area = QHBoxLayout(area_widget)
        area.setContentsMargins(12, 6, 12, 6)
        area.addWidget(QLabel("预设:"))
        self.area_combo = QComboBox()
        for name in AREA_PRESETS:
            self.area_combo.addItem(name)
        self.area_combo.currentTextChanged.connect(self._on_area_preset_changed)
        area.addWidget(self.area_combo)
        area.addSpacing(12)
        self.north_edit = QLineEdit()
        self.north_edit.setPlaceholderText("北纬")
        self.west_edit = QLineEdit()
        self.west_edit.setPlaceholderText("西经")
        self.south_edit = QLineEdit()
        self.south_edit.setPlaceholderText("南纬")
        self.east_edit = QLineEdit()
        self.east_edit.setPlaceholderText("东经")
        for label_text, w in (
            ("N", self.north_edit),
            ("W", self.west_edit),
            ("S", self.south_edit),
            ("E", self.east_edit),
        ):
            w.setFixedWidth(90)
            tag = QLabel(label_text)
            tag.setStyleSheet("color:#64748B; font-weight:600;")
            area.addWidget(tag)
            area.addWidget(w)
        area.addStretch(1)

        # 输出（左列）
        out_widget = QWidget()
        out = QHBoxLayout(out_widget)
        out.setContentsMargins(12, 6, 12, 6)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["netcdf", "grib"])
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("选择保存目录")
        browse_btn = QPushButton("浏览…")
        browse_btn.setToolTip("选择文件保存目录")
        browse_btn.setProperty("btnClass", "secondary")
        browse_btn.clicked.connect(self._browse_dir)
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("留空自动命名")
        out.addWidget(QLabel("格式:"))
        out.addWidget(self.format_combo)
        out.addWidget(QLabel("目录:"))
        out.addWidget(self.dir_edit, 1)
        out.addWidget(browse_btn)
        out.addWidget(QLabel("文件名:"))
        out.addWidget(self.filename_edit, 1)

        # 下载任务（中央）
        task_widget = QWidget()
        task = QVBoxLayout(task_widget)
        task.setContentsMargins(12, 6, 12, 6)
        self.task_table = QTableWidget(0, 4)
        self.task_table.setHorizontalHeaderLabels(["序号", "任务描述", "状态", "进度"])
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.task_table.setColumnWidth(0, 50)
        self.task_table.setColumnWidth(2, 80)
        task.addWidget(self.task_table, 1)
        task_btns = QHBoxLayout()
        add_task_btn = QPushButton("添加任务")
        add_task_btn.setToolTip("把当前配置加入下载队列，按顺序串行下载")
        add_task_btn.clicked.connect(self._add_task)
        cancel_btn = QPushButton("取消选中")
        cancel_btn.setToolTip("取消选中的排队任务（下载中的任务不可中断）")
        cancel_btn.setProperty("btnClass", "ghost")
        cancel_btn.clicked.connect(self._cancel_selected)
        clear_btn = QPushButton("清空已完成")
        clear_btn.setToolTip("移除已完成/失败/已取消的任务行")
        clear_btn.setProperty("btnClass", "ghost")
        clear_btn.clicked.connect(self._clear_finished)
        task_btns.addWidget(add_task_btn)
        task_btns.addWidget(cancel_btn)
        task_btns.addWidget(clear_btn)
        task_btns.addStretch(1)
        task.addLayout(task_btns)

        # 下载日志（底部）
        log_widget = QWidget()
        log = QVBoxLayout(log_widget)
        log.setContentsMargins(12, 6, 12, 6)
        log_head = QHBoxLayout()
        log_title = QLabel("下载日志")
        log_title.setStyleSheet("color:#1E3A8A; font-weight:600;")
        log_head.addWidget(log_title)
        log_head.addStretch(1)
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setToolTip("清空当前日志内容")
        clear_log_btn.setProperty("btnClass", "ghost")
        clear_log_btn.clicked.connect(self._clear_log)
        log_head.addWidget(clear_log_btn)
        log.addLayout(log_head)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        log.addWidget(self.log_view)

        # 横屏分栏：左列配置 / 右列请求参数 / 中央任务 / 底部日志，均可持续拖动
        self.setCentralWidget(task_widget)
        self._make_dock("数据集与气象要素", sel_widget, 120, Qt.LeftDockWidgetArea)
        self._make_dock("区域", area_widget, 60, Qt.LeftDockWidgetArea)
        self._make_dock("时间范围", time_widget, 60, Qt.LeftDockWidgetArea)
        self._make_dock("输出", out_widget, 60, Qt.LeftDockWidgetArea)
        self._make_dock("请求参数", req_widget, 240, Qt.RightDockWidgetArea)
        self._make_dock("下载日志", log_widget, 140, Qt.BottomDockWidgetArea)
        self._on_dataset_changed(self.ds_combo.currentText())  # 初始化默认数据集（log_view 已就绪）

    # ---------- 数据集与气象要素 ----------
    def _on_dataset_changed(self, name):
        """数据集切换：联动数据集 ID、气象要素列表与参数预填。"""
        dataset = DATASET_CATALOG.get(name)
        if not dataset:  # 自定义…
            self.dataset_edit.clear()
            self.dataset_edit.setFocus()
            self.time_edit.setEnabled(True)
            self.time_edit.setPlaceholderText("如 00,06,12,18（留空 = 全部时次）")
            return
        self.dataset_edit.setText(dataset)
        self.var_combo.clear()
        self.var_combo.addItems(DATASET_VARIABLES.get(dataset, []))

        # 月平均 / 日统计数据集无需"时次"参数
        no_time = "月平均" in name or "daily-statistics" in dataset
        self.time_edit.setEnabled(not no_time)
        self.time_edit.setPlaceholderText(
            "该数据集无需时次（月平均/日统计）" if no_time else "如 00,06,12,18（留空 = 全部时次）"
        )
        if no_time:
            self.time_edit.clear()

        # 清理上一数据集的专属参数，再预填当前数据集参数
        self._remove_param("pressure_level")
        self._remove_param("statistic")
        self._remove_param("daily_statistic")
        self._remove_param("frequency")
        self._remove_param("product_type")
        if "land" not in dataset:  # ERA5-Land 无 product_type 参数
            self._ensure_param("product_type", "monthly_averaged_reanalysis" if "月平均" in name else "reanalysis")
        if "pressure-levels" in dataset:
            self._ensure_param("pressure_level", "850")
        if "daily-statistics" in dataset:
            # 日统计（derived）数据集参数：daily_statistic / frequency / time_zone
            self._ensure_param("daily_statistic", "daily_mean")
            self._ensure_param("frequency", "1_hourly")
        self._append_log(f"数据集：{name}（{dataset}）")

    def _on_variable_changed(self, text):
        """气象要素变化：同步到参数表的 variable 行。"""
        value = str(text).strip()
        if not value:
            return
        for row in range(self.params_table.rowCount()):
            item = self.params_table.item(row, 0)
            if item and item.text().strip() == "variable":
                self.params_table.item(row, 1).setText(value)
                return
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem("variable"))
        self.params_table.setItem(row, 1, QTableWidgetItem(value))

    def _ensure_param(self, key: str, value: str):
        """参数表中若没有 key 行则新增，已有且值为空则补默认值。"""
        for row in range(self.params_table.rowCount()):
            item = self.params_table.item(row, 0)
            if item and item.text().strip() == key:
                value_item = self.params_table.item(row, 1)
                if not (value_item and value_item.text().strip()):
                    self.params_table.item(row, 1).setText(value)
                return
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem(key))
        self.params_table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_param(self, key: str):
        """删除参数表中指定参数行。"""
        for row in range(self.params_table.rowCount()):
            item = self.params_table.item(row, 0)
            if item and item.text().strip() == key:
                self.params_table.removeRow(row)
                return

    # ---------- 参数表 ----------
    def _add_param_row(self):
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem(""))
        self.params_table.setItem(row, 1, QTableWidgetItem(""))

    def _del_param_row(self):
        rows = sorted({idx.row() for idx in self.params_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.params_table.removeRow(row)

    # ---------- 区域 ----------
    def _on_area_preset_changed(self, text):
        area = AREA_PRESETS.get(text)
        if area is None:
            for w in (self.north_edit, self.west_edit, self.south_edit, self.east_edit):
                w.clear()
            return
        self.north_edit.setText(str(area[0]))
        self.west_edit.setText(str(area[1]))
        self.south_edit.setText(str(area[2]))
        self.east_edit.setText(str(area[3]))

    # ---------- 输出 ----------
    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.dir_edit.text())
        if path:
            self.dir_edit.setText(path)

    # ---------- 任务 ----------
    def _collect_request(self):
        dataset = self.dataset_edit.text().strip()
        if not dataset:
            raise ValueError("请填写数据集名称")
        params = {}
        for row in range(self.params_table.rowCount()):
            name_item = self.params_table.item(row, 0)
            value_item = self.params_table.item(row, 1)
            if name_item and name_item.text().strip():
                params[name_item.text().strip()] = value_item.text().strip() if value_item else ""
        area = self._current_area()
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        times = normalize_times(self.time_edit.text())
        if times is None and self.time_edit.isEnabled():
            # 时次留空且输入框可用（小时数据集）=> 默认请求全部 24 个时次，
            # 而不是让 CDS 按默认值只给个别时次
            times = [f"{h:02d}:00" for h in range(24)]
        # 日统计（derived）数据集改用 year/month/day 参数，且无需时次
        use_ymd = "daily-statistics" in dataset
        return dataset, build_request(
            params, area, f"{start}/{end}", times,
            self.format_combo.currentText(), use_ymd=use_ymd,
        )

    def _current_area(self):
        if self.area_combo.currentText() == "全球":
            return None
        try:
            values = [float(w.text().strip()) for w in (self.north_edit, self.west_edit, self.south_edit, self.east_edit)]
        except ValueError:
            raise ValueError("请填写完整的经纬度范围（北纬/西经/南纬/东经）")
        return values  # [N, W, S, E]

    def _add_task(self):
        try:
            dataset, request = self._collect_request()
        except ValueError as exc:
            QMessageBox.warning(self, "参数不完整", str(exc))
            return
        out_dir = self.dir_edit.text().strip()
        if not out_dir or not Path(out_dir).is_dir():
            QMessageBox.warning(self, "参数不完整", "请选择有效的输出目录。")
            return
        filename = self.filename_edit.text().strip()
        if not filename:
            ext = "grib" if request.get("data_format") == "grib" else "nc"
            start = self.start_date.date().toString("yyyyMMdd")
            end = self.end_date.date().toString("yyyyMMdd")
            filename = f"{dataset}_{start}_{end}.{ext}"
        target = str(Path(out_dir) / filename)
        desc = (
            f"{dataset} | {self.area_combo.currentText()} | "
            f"{self.start_date.date().toString('yyyy-MM-dd')}~{self.end_date.date().toString('yyyy-MM-dd')}"
        )
        task_id = self.worker.add_task(dataset, request, target, desc)
        self._add_task_row(task_id, desc)
        self._append_log(f"[{task_id}] 任务已添加：{desc} → {target}")

    def _add_task_row(self, task_id, desc):
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        self.task_table.setItem(row, 0, QTableWidgetItem(str(task_id)))
        self.task_table.setItem(row, 1, QTableWidgetItem(desc))
        self.task_table.setItem(row, 2, QTableWidgetItem("排队中"))
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setValue(0)
        self.task_table.setCellWidget(row, 3, bar)
        return row

    def _row_of_task(self, task_id: int) -> int | None:
        """按任务序号在表格中查找所在行（行号可能因清空已完成而变动）。"""
        for row in range(self.task_table.rowCount()):
            item = self.task_table.item(row, 0)
            if item and item.text() == str(task_id):
                return row
        return None

    def _cancel_selected(self):
        rows = {idx.row() for idx in self.task_table.selectedIndexes()}
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要取消的任务行。")
            return
        for row in rows:
            task_id = int(self.task_table.item(row, 0).text())
            self.worker.cancel_task(task_id)

    def _clear_finished(self):
        done_statuses = {"完成", "失败", "已取消"}
        for row in range(self.task_table.rowCount() - 1, -1, -1):
            status_item = self.task_table.item(row, 2)
            if status_item and status_item.text() in done_statuses:
                self.task_table.removeRow(row)

    # ---------- 信号回调 ----------
    def _on_task_status(self, task_id, status):
        row = self._row_of_task(task_id)
        if row is None:
            return
        item = self.task_table.item(row, 2)
        item.setText(status)
        status_colors = {
            "排队中": "#64748B",
            "下载中": "#1E40AF",
            "完成": "#16A34A",
            "失败": "#DC2626",
            "已取消": "#94A3B8",
        }
        item.setForeground(QColor(status_colors.get(status, "#334155")))

    def _on_task_progress(self, task_id, percent):
        row = self._row_of_task(task_id)
        if row is None:
            return
        bar = self.task_table.cellWidget(row, 3)
        if percent < 0:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(percent)

    def _on_license_error(self, dataset, message):
        """数据集使用条款未同意（403）：弹窗引导，一键打开同意页面。"""
        url = f"https://cds.climate.copernicus.eu/datasets/{dataset}?tab=download#manage-licences"
        box = QMessageBox(self)
        box.setWindowTitle("需要同意数据条款")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"数据集「{dataset}」的使用条款尚未同意，本次下载已被服务端拒绝。")
        box.setInformativeText("请在 CDS 网页登录并勾选同意该数据集的使用条款，之后重新添加任务即可正常下载。")
        open_btn = box.addButton("打开同意页面", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(url))

    def _clear_log(self):
        self.log_view.clear()

    def _log_color(self, msg: str) -> str | None:
        """按日志关键字返回颜色（深色控制台背景下的亮色系）。"""
        if any(k in msg for k in ("失败", "错误", "404", "未同意", "拒绝")):
            return "#F87171"
        if "已取消" in msg:
            return "#94A3B8"
        if any(k in msg for k in ("完成", "成功")):
            return "#4ADE80"
        if any(k in msg for k in ("任务已添加", "下载中", "数据集：", "队列", "等待")):
            return "#93C5FD"
        return None

    def _append_log(self, msg):
        color = self._log_color(msg)
        if color:
            self.log_view.appendHtml(f'<span style="color:{color};">{html.escape(msg)}</span>')
        else:
            self.log_view.appendPlainText(msg)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())
