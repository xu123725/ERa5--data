"""数据处理页：合并 / 裁剪 / 转 CSV。"""

import xarray as xr

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.processor import crop_netcdf, merge_netcdf, netcdf_to_csv
from app.ui.worker import FunctionWorker

def _card_title(text: str):
    """卡片标题（内置 QGroupBox 标题在某些系统下会被遮挡，改用独立标签）。"""
    label = QLabel(text)
    label.setObjectName("cardTitle")
    return label


class ProcessTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(16)

        # ---- 合并 ----
        merge_box = QGroupBox()
        merge = QVBoxLayout(merge_box)
        merge.addWidget(_card_title("合并多个 netCDF 文件"))
        self.merge_list = QListWidget()
        merge.addWidget(self.merge_list)
        merge_btns = QHBoxLayout()
        add_files_btn = QPushButton("添加文件…")
        add_files_btn.setProperty("btnClass", "secondary")
        add_files_btn.clicked.connect(self._add_merge_files)
        remove_file_btn = QPushButton("移除选中")
        remove_file_btn.setProperty("btnClass", "ghost")
        remove_file_btn.clicked.connect(
            lambda: [self.merge_list.takeItem(i) for i in reversed([idx.row() for idx in self.merge_list.selectedIndexes()])]
        )
        merge_btns.addWidget(add_files_btn)
        merge_btns.addWidget(remove_file_btn)
        merge_btns.addStretch(1)
        merge.addLayout(merge_btns)
        merge_row = QHBoxLayout()
        self.merge_out_edit = QLineEdit()
        self.merge_out_edit.setPlaceholderText("输出 .nc 文件路径")
        browse_btn = QPushButton("浏览…")
        browse_btn.setProperty("btnClass", "secondary")
        browse_btn.clicked.connect(lambda: self._browse_save(self.merge_out_edit, "netCDF (*.nc)"))
        run_merge_btn = QPushButton("执行合并")
        run_merge_btn.clicked.connect(self._run_merge)
        merge_row.addWidget(self.merge_out_edit, 1)
        merge_row.addWidget(browse_btn)
        merge_row.addWidget(run_merge_btn)
        merge.addLayout(merge_row)
        self.merge_status = QLabel("")
        merge.addWidget(self.merge_status)
        layout.addWidget(merge_box)

        # ---- 裁剪 ----
        crop_box = QGroupBox()
        crop = QVBoxLayout(crop_box)
        crop.addWidget(_card_title("按经纬度裁剪"))
        crop_row = QHBoxLayout()
        self.crop_input_edit = QLineEdit()
        self.crop_input_edit.setPlaceholderText("输入 .nc 文件")
        crop_in_btn = QPushButton("浏览…")
        crop_in_btn.setProperty("btnClass", "secondary")
        crop_in_btn.clicked.connect(lambda: self._browse_open(self.crop_input_edit, "netCDF (*.nc)"))
        crop_row.addWidget(self.crop_input_edit, 1)
        crop_row.addWidget(crop_in_btn)
        crop.addLayout(crop_row)
        bounds_row = QHBoxLayout()
        self.crop_north = QLineEdit()
        self.crop_west = QLineEdit()
        self.crop_south = QLineEdit()
        self.crop_east = QLineEdit()
        for w, ph in (
            (self.crop_north, "北纬"),
            (self.crop_west, "西经"),
            (self.crop_south, "南纬"),
            (self.crop_east, "东经"),
        ):
            w.setPlaceholderText(ph)
            w.setFixedWidth(90)
            bounds_row.addWidget(w)
        bounds_row.addStretch(1)
        crop.addLayout(bounds_row)
        crop_row2 = QHBoxLayout()
        self.crop_out_edit = QLineEdit()
        self.crop_out_edit.setPlaceholderText("输出 .nc 文件路径")
        crop_out_btn = QPushButton("浏览…")
        crop_out_btn.setProperty("btnClass", "secondary")
        crop_out_btn.clicked.connect(lambda: self._browse_save(self.crop_out_edit, "netCDF (*.nc)"))
        run_crop_btn = QPushButton("执行裁剪")
        run_crop_btn.clicked.connect(self._run_crop)
        crop_row2.addWidget(self.crop_out_edit, 1)
        crop_row2.addWidget(crop_out_btn)
        crop_row2.addWidget(run_crop_btn)
        crop.addLayout(crop_row2)
        self.crop_status = QLabel("")
        crop.addWidget(self.crop_status)
        layout.addWidget(crop_box)

        # ---- 转 CSV ----
        csv_box = QGroupBox()
        csv = QVBoxLayout(csv_box)
        csv.addWidget(_card_title("netCDF 转 CSV"))
        csv_row = QHBoxLayout()
        self.csv_input_edit = QLineEdit()
        self.csv_input_edit.setPlaceholderText("输入 .nc 文件")
        csv_in_btn = QPushButton("浏览…")
        csv_in_btn.setProperty("btnClass", "secondary")
        csv_in_btn.clicked.connect(lambda: self._browse_open(self.csv_input_edit, "netCDF (*.nc)"))
        self.csv_input_edit.textChanged.connect(self._on_csv_input_changed)
        csv_row.addWidget(self.csv_input_edit, 1)
        csv_row.addWidget(csv_in_btn)
        csv.addLayout(csv_row)
        csv_opts = QHBoxLayout()
        csv_opts.addWidget(QLabel("变量:"))
        self.csv_var_combo = QComboBox()
        self.csv_var_combo.setEditable(True)
        self.csv_var_combo.setPlaceholderText("选择或输入变量名")
        csv_opts.addWidget(self.csv_var_combo, 1)
        csv_opts.addWidget(QLabel("输出:"))
        self.csv_out_edit = QLineEdit()
        self.csv_out_edit.setPlaceholderText("输出 .csv 路径")
        csv_out_btn = QPushButton("浏览…")
        csv_out_btn.setProperty("btnClass", "secondary")
        csv_out_btn.clicked.connect(lambda: self._browse_save(self.csv_out_edit, "CSV (*.csv)"))
        run_csv_btn = QPushButton("导出 CSV")
        run_csv_btn.clicked.connect(self._run_csv)
        csv_opts.addWidget(self.csv_out_edit, 1)
        csv_opts.addWidget(csv_out_btn)
        csv_opts.addWidget(run_csv_btn)
        csv.addLayout(csv_opts)
        self.csv_status = QLabel("")
        csv.addWidget(self.csv_status)
        layout.addWidget(csv_box)

        layout.addStretch(1)

    # ---------- 工具 ----------
    def _browse_open(self, edit, filter_text):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter_text)
        if path:
            edit.setText(path)

    def _browse_save(self, edit, filter_text):
        path, _ = QFileDialog.getSaveFileName(self, "保存为", "", filter_text)
        if path:
            edit.setText(path)

    def _add_merge_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 netCDF 文件", "", "netCDF (*.nc)")
        for p in paths:
            if self.merge_list.findItems(p, Qt.MatchExactly):
                continue
            self.merge_list.addItem(p)

    def _on_csv_input_changed(self, path):
        path = path.strip()
        if not path or not path.lower().endswith(".nc"):
            return
        from app.core.processor import _open_dataset

        ds = None
        cleanup = lambda: None
        try:
            try:
                ds = xr.open_dataset(path)
            except OSError:  # 中文路径：netCDF4 打不开，走 ASCII 临时文件绕行
                ds, cleanup = _open_dataset(path)
            vars_ = [str(v) for v in ds.data_vars]
        except Exception:  # noqa: BLE001 - 允许手动输入变量名
            self.csv_var_combo.setPlaceholderText("识别失败，请手动输入变量名")
            return
        finally:
            if ds is not None:
                ds.close()
            cleanup()
        if not vars_:
            self.csv_var_combo.setPlaceholderText("未发现数据变量，请手动输入")
            return
        self.csv_var_combo.clear()
        self.csv_var_combo.addItems(vars_)
        self.csv_var_combo.setCurrentIndex(0)
        self.csv_status.setText("已识别变量：" + "、".join(vars_))

    def _set_status(self, label: QLabel, text: str, color: str | None = None):
        """设置状态文本并着色（None=恢复默认灰色）。"""
        label.setText(text)
        label.setStyleSheet(f"color:{color}; font-weight:600;" if color else "")

    def _start_job(self, fn, args, status_label, done_msg):
        worker = FunctionWorker(fn, *args, parent=self)
        worker.result_ready.connect(lambda _, lbl=status_label, msg=done_msg: self._set_status(lbl, msg, "#16A34A"))
        worker.failed.connect(lambda msg, lbl=status_label: self._on_job_failed(lbl, msg))
        worker.finished.connect(worker.deleteLater)
        self._set_status(status_label, "处理中…", "#1E40AF")
        self._workers.append(worker)
        worker.start()

    def _on_job_failed(self, label, msg):
        self._set_status(label, "失败", "#DC2626")
        QMessageBox.critical(self, "处理失败", msg)

    # ---------- 执行 ----------
    def _run_merge(self):
        files = [self.merge_list.item(i).text() for i in range(self.merge_list.count())]
        out = self.merge_out_edit.text().strip()
        if not files or not out:
            QMessageBox.warning(self, "提示", "请选择输入文件和输出路径。")
            return
        self._start_job(merge_netcdf, (files, out), self.merge_status, "合并完成")

    def _run_crop(self):
        src = self.crop_input_edit.text().strip()
        out = self.crop_out_edit.text().strip()
        try:
            bounds = [float(self.crop_north.text()), float(self.crop_west.text()),
                      float(self.crop_south.text()), float(self.crop_east.text())]
        except ValueError:
            QMessageBox.warning(self, "提示", "请填写合法的经纬度范围。")
            return
        if not src or not out:
            QMessageBox.warning(self, "提示", "请选择输入文件和输出路径。")
            return
        self._start_job(crop_netcdf, (src, *bounds, out), self.crop_status, "裁剪完成")

    def _run_csv(self):
        src = self.csv_input_edit.text().strip()
        out = self.csv_out_edit.text().strip()
        var = self.csv_var_combo.currentText().strip()
        if not src or not out or not var:
            QMessageBox.warning(self, "提示", "请选择输入文件、变量和输出路径。")
            return
        self._start_job(netcdf_to_csv, (src, var, out), self.csv_status, "导出完成")
