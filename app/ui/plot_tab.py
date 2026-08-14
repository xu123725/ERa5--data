"""绘图页：ERA5 数据可视化（空间分布 / 时间序列 / 垂直剖面）。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

import xarray as xr

from app.core import plotter
from app.core.processor import _open_dataset, time_name

PLOT_TYPES = ["空间分布图", "时间序列图", "垂直剖面图"]

def _card_title(text: str):
    """卡片标题（内置 QGroupBox 标题在某些系统下会被遮挡，改用独立标签）。"""
    label = QLabel(text)
    label.setObjectName("cardTitle")
    return label


class PlotTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(16)

        # 数据选择
        data_box = QGroupBox()
        data_col = QVBoxLayout(data_box)
        data_col.setSpacing(6)
        data_col.addWidget(_card_title("数据"))
        data = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("选择 .nc 文件（ERA5 下载或导入均可）")
        self.file_edit.textChanged.connect(self._on_file_changed)
        browse_btn = QPushButton("浏览…")
        browse_btn.setProperty("btnClass", "secondary")
        browse_btn.clicked.connect(self._browse_file)
        data.addWidget(self.file_edit, 1)
        data.addWidget(browse_btn)
        data.addWidget(QLabel("变量:"))
        self.var_combo = QComboBox()
        self.var_combo.setEditable(True)
        self.var_combo.setPlaceholderText("选择或输入变量名")
        self.var_combo.currentTextChanged.connect(self._on_var_changed)
        data.addWidget(self.var_combo, 1)
        data_col.addLayout(data)
        layout.addWidget(data_box)

        # 图型与参数
        opt_box = QGroupBox()
        opt = QVBoxLayout(opt_box)
        opt.setSpacing(6)
        opt.addWidget(_card_title("图型与参数"))
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("图型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(PLOT_TYPES)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo)
        type_row.addSpacing(16)
        type_row.addWidget(QLabel("区域(留空=全图):"))
        self.north_edit = QLineEdit()
        self.west_edit = QLineEdit()
        self.south_edit = QLineEdit()
        self.east_edit = QLineEdit()
        for label_text, w, ph in (
            ("N", self.north_edit, "北纬"),
            ("W", self.west_edit, "西经"),
            ("S", self.south_edit, "南纬"),
            ("E", self.east_edit, "东经"),
        ):
            w.setPlaceholderText(ph)
            w.setFixedWidth(70)
            tag = QLabel(label_text)
            tag.setStyleSheet("color:#64748B; font-weight:600;")
            type_row.addWidget(tag)
            type_row.addWidget(w)
        type_row.addSpacing(16)
        type_row.addWidget(QLabel("色带:"))
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["viridis", "coolwarm", "RdBu_r", "terrain", "jet"])
        type_row.addWidget(self.cmap_combo)
        type_row.addStretch(1)
        opt.addLayout(type_row)

        self.param_stack = QStackedWidget()
        # 空间分布参数
        map_widget = QWidget()
        map_ = QHBoxLayout(map_widget)
        map_.setContentsMargins(0, 0, 0, 0)
        map_.addWidget(QLabel("时刻:"))
        self.time_combo = QComboBox()
        self.time_combo.addItem("全部时次平均")
        map_.addWidget(self.time_combo, 1)
        self.basemap_cb = QCheckBox("显示海岸线/国界底图")
        self.basemap_cb.setChecked(plotter.has_basemap())
        self.basemap_cb.setEnabled(plotter.has_basemap())
        if not plotter.has_basemap():
            self.basemap_cb.setToolTip("cartopy 未安装，底图不可用")
        map_.addWidget(self.basemap_cb)
        self.param_stack.addWidget(map_widget)
        # 时间序列参数
        ts_widget = QWidget()
        ts = QHBoxLayout(ts_widget)
        ts.setContentsMargins(0, 0, 0, 0)
        ts.addWidget(QLabel("区域内平均值随时间变化"))
        ts.addStretch(1)
        self.param_stack.addWidget(ts_widget)
        # 垂直剖面参数
        prof_widget = QWidget()
        prof = QHBoxLayout(prof_widget)
        prof.setContentsMargins(0, 0, 0, 0)
        prof.addWidget(QLabel("剖面方向:"))
        self.prof_along = QComboBox()
        self.prof_along.addItems(["沿纬度（固定经度）", "沿经度（固定纬度）"])
        prof.addWidget(self.prof_along)
        prof.addWidget(QLabel("固定位置:"))
        self.prof_section = QLineEdit()
        self.prof_section.setPlaceholderText("留空=取中间值")
        self.prof_section.setFixedWidth(120)
        prof.addWidget(self.prof_section)
        prof.addStretch(1)
        self.param_stack.addWidget(prof_widget)
        opt.addWidget(self.param_stack)
        layout.addWidget(opt_box)

        # 画布
        self._fig = Figure(figsize=(8, 5.5))
        self.canvas = FigureCanvasQTAgg(self._fig)
        toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas, 1)

        # 操作行
        op_row = QHBoxLayout()
        plot_btn = QPushButton("绘图")
        plot_btn.clicked.connect(self._plot)
        save_btn = QPushButton("保存 PNG")
        save_btn.clicked.connect(self._save_png)
        op_row.addWidget(plot_btn)
        op_row.addWidget(save_btn)
        self.crop_cb = QCheckBox("保存时裁剪空白")
        self.crop_cb.setChecked(True)
        self.crop_cb.setToolTip("保存 PNG 时自动裁剪四周留白，只保留图形内容")
        op_row.addWidget(self.crop_cb)
        self.status = QLabel("")
        op_row.addWidget(self.status, 1)
        layout.addLayout(op_row)

    # ---------- 数据 ----------
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 netCDF 文件", "", "netCDF (*.nc)")
        if path:
            self.file_edit.setText(path)

    def _on_file_changed(self, path):
        """文件变化：一次打开读取变量列表，并缓存各变量时间坐标。"""
        path = path.strip()
        if not path.lower().endswith(".nc"):
            return
        ds = None
        cleanup = lambda: None
        try:
            try:
                ds = xr.open_dataset(path)
            except OSError:
                ds, cleanup = _open_dataset(path)
            vars_ = [str(v) for v in ds.data_vars]
            # 一次性缓存各变量时间值，切换变量时不再重复打开文件
            self._times_cache = {}
            for v in vars_:
                try:
                    da = ds[v]
                    tname = time_name(da)
                    if tname and da[tname].size:
                        self._times_cache[v] = [str(t)[:19] for t in da[tname].values]
                except Exception:  # noqa: BLE001 - 无时间维的变量不缓存
                    continue
        except Exception:  # noqa: BLE001 - 允许手动输入
            self.var_combo.clear()
            self.var_combo.setPlaceholderText("识别失败，请手动输入变量名")
            self.time_combo.clear()
            self.time_combo.addItem("全部时次平均")
            return
        finally:
            if ds is not None:
                ds.close()
            cleanup()
        if not vars_:
            return
        self.var_combo.clear()
        self.var_combo.addItems(vars_)
        self.var_combo.setCurrentIndex(0)

    def _on_var_changed(self, var):
        if not var or not var.strip():
            return
        self._populate_times()

    def _populate_times(self):
        """按当前变量的时间维度填充"时刻"下拉框。

        优先读缓存（避免重复打开文件）；缓存缺失时回退为直接读取文件，
        保证任何情况下都能识别时次。
        """
        var = self.var_combo.currentText().strip()
        if not var:
            return
        current = self.time_combo.currentText()
        self.time_combo.clear()
        self.time_combo.addItem("全部时次平均")
        times = getattr(self, "_times_cache", {}).get(var)
        if not times:
            times = self._read_times_from_file(var)
            if times:
                if not hasattr(self, "_times_cache"):
                    self._times_cache = {}
                self._times_cache[var] = times
        if times:
            self.time_combo.addItems(times)
        idx = self.time_combo.findText(current)
        if idx >= 0:
            self.time_combo.setCurrentIndex(idx)

    def _read_times_from_file(self, var):
        """打开文件读取指定变量的时间坐标（缓存兜底）。"""
        path = self.file_edit.text().strip()
        if not path:
            return []
        ds = None
        cleanup = lambda: None
        try:
            try:
                ds = xr.open_dataset(path)
            except OSError:
                ds, cleanup = _open_dataset(path)
            if var not in ds:
                return []
            da = ds[var]
            tname = time_name(da)
            if not tname or not da[tname].size:
                return []
            return [str(t)[:19] for t in da[tname].values]
        except Exception:  # noqa: BLE001 - 读取失败则无时次可选
            return []
        finally:
            if ds is not None:
                ds.close()
            cleanup()

    # ---------- 状态 ----------
    def _set_status(self, text: str, color: str | None = None):
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{color}; font-weight:600;" if color else "")

    # ---------- 绘图 ----------
    def _area_values(self):
        texts = [w.text().strip() for w in (self.north_edit, self.west_edit, self.south_edit, self.east_edit)]
        if all(t == "" for t in texts):
            return None
        if any(t == "" for t in texts):
            raise ValueError("请完整填写区域（北/西/南/东）或全部留空")
        try:
            return [float(t) for t in texts]
        except ValueError:
            raise ValueError("区域必须为数字（经纬度）")

    def _plot(self):
        src = self.file_edit.text().strip()
        var = self.var_combo.currentText().strip()
        if not src or not var:
            QMessageBox.warning(self, "提示", "请先选择文件和变量。")
            return
        try:
            area = self._area_values()
        except ValueError as exc:
            QMessageBox.warning(self, "提示", str(exc))
            return
        self._set_status("绘图中…", "#1E40AF")
        QApplication.processEvents()
        try:
            self._fig.clear()
            if self.type_combo.currentText() == "空间分布图" and plotter.HAS_CARTOPY:
                import cartopy.crs as ccrs

                ax = self._fig.add_subplot(111, projection=ccrs.PlateCarree())
            else:
                ax = self._fig.add_subplot(111)
            ptype = self.type_combo.currentText()
            cmap = self.cmap_combo.currentText()
            if ptype == "空间分布图":
                idx = self.time_combo.currentIndex()
                time_step = None if idx <= 0 else idx - 1
                plotter.plot_map(
                    src, var, time_step=time_step,
                    north=area[0] if area else None, west=area[1] if area else None,
                    south=area[2] if area else None, east=area[3] if area else None,
                    cmap=cmap, show_basemap=self.basemap_cb.isChecked(), ax=ax,
                )
            elif ptype == "时间序列图":
                plotter.plot_timeseries(
                    src, var,
                    north=area[0] if area else None, west=area[1] if area else None,
                    south=area[2] if area else None, east=area[3] if area else None,
                    ax=ax,
                )
            else:
                along = "lat" if self.prof_along.currentIndex() == 0 else "lon"
                sec_text = self.prof_section.text().strip()
                section = float(sec_text) if sec_text else None
                plotter.plot_profile(
                    src, var, along=along, section=section,
                    north=area[0] if area else None, west=area[1] if area else None,
                    south=area[2] if area else None, east=area[3] if area else None,
                    cmap=cmap, ax=ax,
                )
            self.canvas.draw()
            self._set_status("绘图完成，可保存 PNG", "#16A34A")
        except Exception as exc:  # noqa: BLE001
            self._set_status("绘图失败", "#DC2626")
            QMessageBox.critical(self, "绘图失败", str(exc))

    def _save_png(self):
        var = self.var_combo.currentText().strip() or "plot"
        ptype = self.type_combo.currentText()
        path, _ = QFileDialog.getSaveFileName(self, "保存图片", f"{var}_{ptype}.png", "PNG (*.png)")
        if not path:
            return
        try:
            kwargs = {}
            if self.crop_cb.isChecked():
                # bbox_inches='tight' 自动裁剪四周留白，只保留图形与标注内容
                kwargs["bbox_inches"] = "tight"
            self._fig.savefig(path, dpi=150, **kwargs)
            self._set_status(f"已保存：{path}", "#16A34A")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))

    def _on_type_changed(self, _text):
        self.param_stack.setCurrentIndex(self.type_combo.currentIndex())