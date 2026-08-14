"""ERA5 数据绘图：空间分布图 / 时间序列图 / 垂直剖面图。

- 中文字体自动配置（微软雅黑）
- cartopy 底图可选：未安装或导入失败时自动退回纯网格图
- 兼容中文路径与新旧坐标命名（time/lat/lon 与 valid_time/latitude/longitude）
- 绘图接口遵循 matplotlib / cartopy / xarray 官方推荐用法
"""

import numpy as np
import matplotlib.figure as mfig
import matplotlib.pyplot as plt

from app.core.processor import _open_dataset, lat_name, lon_name, sel_area, time_name

# 中文字体与负号显示（须在任何 Figure 创建前设置）
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


def _patch_matplotlib_ui():
    """对 Matplotlib 的 Qt 后端 UI 进行汉化（工具栏提示与子图调节对话框）。"""
    try:
        from matplotlib.backends import backend_qt
        from PySide6 import QtWidgets, QtGui

        # 1. 汉化 NavigationToolbar2QT 的工具栏按钮提示与图标优化
        if hasattr(backend_qt, "NavigationToolbar2QT"):
            # 汉化提示
            translation_map = {
                "Home": ("主页", "重置为原始视图"),
                "Back": ("后退", "回到上一个视图"),
                "Forward": ("前进", "前往下一个视图"),
                "Pan": ("平移", "左键平移，右键缩放\nx/y 固定轴，CTRL 固定比例"),
                "Zoom": ("缩放", "缩放到矩形区域\nx/y 固定轴"),
                "Subplots": ("子图调节", "配置子图参数"),
                "Customize": ("定制", "编辑轴、曲线和图像参数"),
                "Save": ("保存", "保存图片"),
            }
            new_toolitems = []
            for item in backend_qt.NavigationToolbar2QT.toolitems:
                name = item[0]
                if name in translation_map:
                    new_item = (translation_map[name][0], translation_map[name][1], item[2], item[3])
                    new_toolitems.append(new_item)
                else:
                    new_toolitems.append(item)
            backend_qt.NavigationToolbar2QT.toolitems = new_toolitems

            # 优化图标颜色：将工具栏图标设为深蓝色（#1E40AF）以提高对比度
            original_toolbar_init = backend_qt.NavigationToolbar2QT.__init__

            def new_toolbar_init(self, *args, **kwargs):
                 original_toolbar_init(self, *args, **kwargs)
                 self.setStyleSheet("""
                    QToolBar { 
                        background-color: #FFFFFF; 
                        border: 1px solid #DBEAFE; 
                        border-radius: 6px; 
                        padding: 2px; 
                    }
                    QToolButton { 
                        background-color: transparent;
                        border: none; 
                        border-radius: 4px;
                        padding: 4px; 
                        margin: 2px;
                    }
                    QToolButton:hover { 
                        background-color: #E9EEF6; 
                    }
                 """)
                 for btn in self.findChildren(QtWidgets.QToolButton):
                    effect = QtWidgets.QGraphicsColorizeEffect(btn)
                    effect.setColor(QtGui.QColor("#1E40AF"))
                    btn.setGraphicsEffect(effect)

            backend_qt.NavigationToolbar2QT.__init__ = new_toolbar_init

        # 2. 汉化 SubplotToolQt 对话框
        if hasattr(backend_qt, "SubplotToolQt"):
            original_init = backend_qt.SubplotToolQt.__init__

            def new_init(self, targetfig, parent):
                original_init(self, targetfig, parent)
                self.setWindowTitle("子图参数调节")
                self.setStyleSheet("""
                    QDialog { background-color: #FFFFFF; }
                    QGroupBox { font-weight: bold; color: #1E3A8A; }
                    QPushButton { min-width: 80px; }
                """)

                texts = {
                    "Borders": "边距",
                    "top": "上",
                    "bottom": "下",
                    "left": "左",
                    "right": "右",
                    "Spacings": "间距",
                    "hspace": "行间距",
                    "wspace": "列间距",
                    "Export values": "导出数值",
                    "Tight layout": "紧凑布局",
                    "Reset": "重置",
                    "Close": "关闭",
                }

                # 遍历所有子控件进行文本替换
                for group_box in self.findChildren(QtWidgets.QGroupBox):
                    if group_box.title() in texts:
                        group_box.setTitle(texts[group_box.title()])

                for button in self.findChildren(QtWidgets.QPushButton):
                    if button.text() in texts:
                        button.setText(texts[button.text()])

                for label in self.findChildren(QtWidgets.QLabel):
                    if label.text() in texts:
                        label.setText(texts[label.text()])

            backend_qt.SubplotToolQt.__init__ = new_init

        # 3. 汉化"编辑轴、曲线和图像参数"对话框（figureoptions / _formlayout）
        try:
            from matplotlib.backends.qt_editor import _formlayout

            _patch_figureoptions_form(_formlayout)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass


def _patch_figureoptions_form(fl):
    """汉化 matplotlib 的"图形选项"对话框（Customize 按钮触发）。

    通过包装 _formlayout.fedit 实现：
    - 字段键、分组标题、注释全部译为中文；
    - 下拉框选项“显示中文、取值保留英文原值”，避免破坏
      figure_edit 的 apply 回调（如 set_xscale('线性') 会报错）。
    """
    from matplotlib.backends.qt_editor.figureoptions import figure_edit  # noqa: F401

    QtWidgets = fl.QtWidgets

    # 字段键 / 分组标题 / 对话框标题 -> 中文
    LABEL_CN = {
        "Title": "标题",
        "Min": "最小值",
        "Max": "最大值",
        "Label": "标签",
        "Scale": "刻度类型",
        "X-Axis": "X 轴",
        "Y-Axis": "Y 轴",
        "Z-Axis": "Z 轴",
        "Figure options": "图形选项",
        "Axes": "坐标轴",
        "Curves": "曲线",
        "Images, etc.": "图像等",
        "(Re-)Generate automatic legend": "重新生成自动图例",
        "Line style": "线型",
        "Draw style": "绘制方式",
        "Width": "线宽",
        "Color (RGBA)": "颜色 (RGBA)",
        "Style": "样式",
        "Size": "大小",
        "Face color (RGBA)": "填充颜色 (RGBA)",
        "Edge color (RGBA)": "边缘颜色 (RGBA)",
        "Colormap": "色带",
        "Min. value": "最小值",
        "Max. value": "最大值",
        "Interpolation": "插值",
        "Interpolation stage": "插值阶段",
    }
    # 分组内注释（label 为 None 的标题块）
    COMMENT_CN = {
        "<b>X-Axis</b>": "<b>X 轴</b>",
        "<b>Y-Axis</b>": "<b>Y 轴</b>",
        "<b>Z-Axis</b>": "<b>Z 轴</b>",
        "<b>Line</b>": "<b>线条</b>",
        "<b>Marker</b>": "<b>标记</b>",
    }
    # 下拉框选项显示文本 -> 中文（取值仍用英文原值）
    OPT_CN = {
        # 坐标刻度
        "linear": "线性",
        "log": "对数",
        "symlog": "对称对数",
        "logit": "Logit 变换",
        # 线型 / 绘制方式
        "Solid": "实线",
        "Dashed": "虚线",
        "DashDot": "点划线",
        "Dotted": "点线",
        "None": "无",
        "Default": "默认",
        "Steps (Pre)": "阶梯（前）",
        "Steps (Mid)": "阶梯（中）",
        "Steps (Post)": "阶梯（后）",
        # 标记
        "nothing": "无",
        "point": "点",
        "pixel": "像素",
        "circle": "圆形",
        "square": "方形",
        "diamond": "菱形",
        "thin diamond": "细菱形",
        "star": "星形",
        "triangle_up": "上三角",
        "triangle_down": "下三角",
        "triangle_left": "左三角",
        "triangle_right": "右三角",
        "plus": "加号",
        "plus (filled)": "填充加号",
        "x": "叉号",
        "hexagon1": "六边形 1",
        "hexagon2": "六边形 2",
        "octagon": "八边形",
        "pentagon": "五边形",
        "vline": "竖线",
        "hline": "横线",
        "tickleft": "左刻度",
        "tickright": "右刻度",
        "tickup": "上刻度",
        "tickdown": "下刻度",
        "caretleft": "左箭头",
        "caretright": "右箭头",
        "caretup": "上箭头",
        "caretdown": "下箭头",
        "caretleftbase": "左箭头（基线）",
        "caretrightbase": "右箭头（基线）",
        "caretupbase": "上箭头（基线）",
        "caretdownbase": "下箭头（基线）",
        # 插值
        "nearest": "最近邻",
        "bilinear": "双线性",
        "bicubic": "双三次",
        "spline16": "样条 16",
        "spline36": "样条 36",
        "hanning": "汉宁",
        "hamming": "汉明",
        "hermite": "埃尔米特",
        "kaiser": "凯泽",
        "quadric": "二次",
        "catrom": "Catmull-Rom",
        "gaussian": "高斯",
        "bessel": "贝塞尔",
        "mitchell": "米切尔",
        "sinc": "Sinc",
        "lanczos": "兰索斯",
        "blackman": "布莱克曼",
        "none": "无",
        # 插值阶段
        "data": "数据",
        "rgba": "RGBA",
        "auto": "自动",
    }

    def _tr_combobox(value):
        """把下拉配置转成“显示中文、值保留英文”的 (key, 中文) 列表。"""
        value = list(value)
        selindex = value.pop(0)
        items = value
        new_items = []
        if items and isinstance(items[0], (list, tuple)):
            for key, val in items:
                new_items.append((key, OPT_CN.get(str(val), str(val))))
        else:  # 纯字符串选项（如刻度类型）：转为 (key, 中文) 形式
            for opt in items:
                new_items.append((opt, OPT_CN.get(str(opt), str(opt))))
        return [selindex] + new_items

    def _tr_group(group):
        """转换一个表单分组 [(label, value), ...]。"""
        out = []
        for label, value in group:
            if label is None:
                out.append((None, COMMENT_CN.get(value, value) if isinstance(value, str) else value))
            elif isinstance(value, (list, tuple)) and value:
                out.append((LABEL_CN.get(str(label), str(label)), _tr_combobox(value)))
            else:
                out.append((LABEL_CN.get(str(label), str(label)), value))
        return out

    def _tr_data(data):
        """递归转换 datagroup：[(分组, 标题, 注释), ...]。"""
        out = []
        for group, title, comment in data:
            if (isinstance(group, (list, tuple)) and group
                    and isinstance(group[0], (list, tuple)) and len(group[0]) == 3):
                # 子条目是 [子分组, 条目名, 注释]（多条曲线/图像下拉切换）
                sub = []
                for item in group:
                    sub.append((_tr_group(item[0]), item[1], item[2]))
                out.append((sub, LABEL_CN.get(str(title), str(title)), comment))
            else:
                out.append((_tr_group(group), LABEL_CN.get(str(title), str(title)), comment))
        return out

    orig_fedit = fl.fedit

    def _fedit(data, title="", comment="", icon=None, parent=None, apply=None):
        new_data = _tr_data(data)
        new_title = LABEL_CN.get(str(title), str(title))
        if QtWidgets.QApplication.startingUp():
            _app = QtWidgets.QApplication([])
        dialog = fl.FormDialog(new_data, new_title, comment, icon, parent, apply)
        # 汉化标准按钮（确定/取消/应用…）
        for std, text in {
            QtWidgets.QDialogButtonBox.StandardButton.Ok: "确定",
            QtWidgets.QDialogButtonBox.StandardButton.Cancel: "取消",
            QtWidgets.QDialogButtonBox.StandardButton.Apply: "应用",
            QtWidgets.QDialogButtonBox.StandardButton.Close: "关闭",
            QtWidgets.QDialogButtonBox.StandardButton.Help: "帮助",
        }.items():
            btn = dialog.bbox.button(std)
            if btn is not None:
                btn.setText(text)
        if parent is not None:
            if hasattr(parent, "_fedit_dialog"):
                parent._fedit_dialog.close()
            parent._fedit_dialog = dialog
        dialog.show()

    fl.fedit = _fedit


_patch_matplotlib_ui()

try:  # cartopy 底图可选能力
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER

    HAS_CARTOPY = True
except Exception:  # noqa: BLE001 - 底图缺失不影响基础绘图
    HAS_CARTOPY = False


def has_basemap() -> bool:
    """cartopy 底图是否可用。"""
    return HAS_CARTOPY


# 常见气象要素中文名（ERA5 / ERA5-Land 变量名 -> 中文）
VAR_CN = {
    "t2m": "2m 温度",
    "2m_temperature": "2m 温度",
    "d2m": "2m 露点温度",
    "2m_dewpoint_temperature": "2m 露点温度",
    "msl": "海平面气压",
    "mean_sea_level_pressure": "海平面气压",
    "sp": "地表气压",
    "surface_pressure": "地表气压",
    "tp": "总降水",
    "total_precipitation": "总降水",
    "u10": "10m u 风",
    "10m_u_component_of_wind": "10m u 风",
    "v10": "10m v 风",
    "10m_v_component_of_wind": "10m v 风",
    "temperature": "温度",
    "geopotential": "位势高度",
    "u_component_of_wind": "u 风",
    "v_component_of_wind": "v 风",
    "relative_humidity": "相对湿度",
    "specific_humidity": "比湿",
}


def var_cn_name(variable: str) -> str:
    """变量名转中文名；无映射时返回原名。"""
    return VAR_CN.get(variable, variable)


# ERA5 国际单位 -> 国内气象常用单位（变量名 -> (国内单位, 转换函数)）
# 依据 ERA5/ECMWF 官方文档：2m 温度 K、气压 Pa、总降水 m、位势 m^2/s^2、云量 0~1
# 国内业务规范：温度 °C、气压 hPa、位势高度 gpm（位势米）、降水 mm、云量 %
UNITS_CN = {
    "t2m": ("°C", lambda x: x - 273.15),
    "2m_temperature": ("°C", lambda x: x - 273.15),
    "d2m": ("°C", lambda x: x - 273.15),
    "2m_dewpoint_temperature": ("°C", lambda x: x - 273.15),
    "skt": ("°C", lambda x: x - 273.15),
    "skin_temperature": ("°C", lambda x: x - 273.15),
    "sst": ("°C", lambda x: x - 273.15),
    "sea_surface_temperature": ("°C", lambda x: x - 273.15),
    "temperature": ("°C", lambda x: x - 273.15),
    "msl": ("hPa", lambda x: x / 100.0),
    "mean_sea_level_pressure": ("hPa", lambda x: x / 100.0),
    "sp": ("hPa", lambda x: x / 100.0),
    "surface_pressure": ("hPa", lambda x: x / 100.0),
    "tp": ("mm", lambda x: x * 1000.0),
    "total_precipitation": ("mm", lambda x: x * 1000.0),
    # 位势高度：位势 (m^2/s^2) / 标准重力 9.80665 m/s^2 = 位势米 gpm（ECMWF 官方换算）
    "geopotential": ("gpm", lambda x: x / 9.80665),
    "tcc": ("%", lambda x: x * 100.0),
    "total_cloud_cover": ("%", lambda x: x * 100.0),
    "specific_humidity": ("g/kg", lambda x: x * 1000.0),
}


def _convert_units(da):
    """按国内常用单位转换变量（ERA5 国际单位 -> 国内），并更新 units 属性。"""
    entry = UNITS_CN.get(str(da.name or ""))
    if entry is None:
        return da  # 无映射：保持原值（如 m/s 风、相对湿度 %）
    cn_unit, fn = entry
    out = fn(da)
    return out.assign_attrs(units=cn_unit)


def _robust_range(data, lo: float = 1.0, hi: float = 99.0):
    """基于分位数裁剪色标范围。

    直接用数据 min/max 会被极端值拉伸，导致主体颜色平淡、放大后看不清；
    改用 1%~99% 分位数范围可显著提升主体对比度。
    """
    arr = np.asarray(data, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(arr, lo))
    vmax = float(np.percentile(arr, hi))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
        vmin = float(np.nanmin(arr))
        vmax = float(np.nanmax(arr))
    return vmin, vmax


def _var_label(da) -> str:
    """变量轴/色条标签：优先中文名，其次 long_name，附加单位。"""
    name = str(da.name or "")
    label = var_cn_name(name)
    if label == name:
        label = getattr(da, "long_name", None) or label or "数据"
    units = getattr(da, "units", None)
    return f"{label} [{units}]" if units else label


def _add_left_label(ax, label: str):
    """在图像左侧添加竖排的变量名标注（要素名放左边）。

    放在 y 轴刻度标签外侧（-0.12 轴宽处），配合调用方预留的
    左空白（fig.subplots_adjust(left=...)），避免与"纬度/气压层"
    等坐标标签重叠或被画布裁剪。
    """
    ax.text(
        -0.17, 0.5, label,
        transform=ax.transAxes,
        rotation=90,
        va="center", ha="center",
        fontsize=11, color="#1F2937",
    )


def _finalize_figure(fig):
    """绘制收尾：紧凑布局并预留左侧空白，确保变量名标注不被裁剪。"""
    fig.tight_layout()
    fig.subplots_adjust(left=0.2)



def _prep_2d(da, time_step=None, level=None):
    """把变量规整为 (lat, lon) 二维：指定时刻/层，其余非坐标维求平均。

    keep_attrs=True 保留 units/long_name 等元数据——xarray 官方约定归约
    默认丢弃属性，缺省会丢失色条/轴标签单位。
    """
    lat, lon = lat_name(da), lon_name(da)
    tname = time_name(da)
    if tname and time_step is not None:
        da = da.isel({tname: time_step})
    if "pressure_level" in da.dims and level is not None:
        da = da.isel(pressure_level=level)
    for dim in list(da.dims):
        if dim not in (lat, lon):
            da = da.mean(dim=dim, keep_attrs=True)
    return da


def _draw_map(ax, da, cmap, show_basemap, title):
    lat, lon = lat_name(da), lon_name(da)
    lons, lats = da[lon].values, da[lat].values
    ax.set_facecolor("#B0C4DE")  # 海洋底色
    vmin, vmax = _robust_range(da.values)  # 分位数裁剪，提升对比度
    geo = HAS_CARTOPY and getattr(ax, "projection", None) is not None
    if geo:
        # PlateCarree 下经纬度即投影坐标；transform 必须显式声明（cartopy 官方要求）
        mesh = ax.pcolormesh(
            lons, lats, da.values, cmap=cmap, shading="auto",
            vmin=vmin, vmax=vmax, transform=ccrs.PlateCarree(),
        )
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()], crs=ccrs.PlateCarree())
        _decorate_map_axis(ax, show_basemap)
    else:
        mesh = ax.pcolormesh(lons, lats, da.values, cmap=cmap, shading="auto", vmin=vmin, vmax=vmax)
        ax.grid(True, linestyle="--", color="0.7", alpha=0.6)
    cb = ax.figure.colorbar(mesh, ax=ax, orientation="vertical", pad=0.02, shrink=0.9, aspect=30)
    ax.set_xlabel("经度 (°E)", fontsize=11)
    ax.set_ylabel("纬度 (°N)", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", color="#0B223A")
    _add_left_label(ax, _var_label(da))  # 要素名放图像左侧
    return mesh


def _decorate_map_axis(ax, show_basemap):
    """补充海岸线、国家边界与经纬度网格线标注（cartopy GeoAxes）。

    - 海岸线/国界使用 110m 比例尺数据（随 cartopy 离线打包，避免首次联网下载；
      如需更高精度可改用 with_scale("50m")，但需联网下载 Natural Earth 数据）
    - 经纬网格线带数值标注，样式参考 cartopy 官方示例
    """
    try:
        if show_basemap:
            ax.add_feature(cfeature.COASTLINE.with_scale("110m"), edgecolor="#444444", linewidth=0.7)
            ax.add_feature(cfeature.BORDERS.with_scale("110m"), edgecolor="#888888", linewidth=0.6)
    except Exception:  # noqa: BLE001 - 底图数据不可用时不阻塞主图
        pass
    try:
        gl = ax.gridlines(draw_labels=True, linestyle="--", color="0.7", alpha=0.6)
        gl.top_labels = False
        gl.right_labels = False
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER
    except Exception:  # noqa: BLE001 - 网格线异常不阻塞主图
        pass


def _new_ax(figsize=(8, 6), projection=None):
    """创建独立 Figure（不依赖 pyplot 全局状态，matplotlib 官方推荐）。"""
    fig = mfig.Figure(figsize=figsize)
    ax = fig.add_subplot(111, projection=projection)
    return fig, ax


def plot_map(
    file_path,
    variable,
    time_step=None,
    level=None,
    north=None,
    west=None,
    south=None,
    east=None,
    cmap="viridis",
    show_basemap=True,
    title=None,
    ax=None,
    save_path=None,
):
    """空间分布图：某时刻/层的 (lat, lon) 平面图。返回 figure。"""
    ds, cleanup = _open_dataset(file_path)
    try:
        da = ds[variable]
        if north is not None:
            da = sel_area(da, north, west, south, east)
        da = _convert_units(_prep_2d(da, time_step, level).load())
    finally:
        ds.close()
        cleanup()

    if ax is None:
        projection = ccrs.PlateCarree() if HAS_CARTOPY else None
        fig, ax = _new_ax(projection=projection)
    else:
        # 由调用方传入的轴：不再 clear（cartopy 官方警告：在 GeoAxes 上
        # 调用 clear()/cla() 会破坏投影状态，应传入新轴）
        fig = ax.figure
    _draw_map(ax, da, cmap, show_basemap, title or f"{var_cn_name(variable)} 空间分布")
    _finalize_figure(fig)
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
    return fig


def plot_timeseries(
    file_path,
    variable,
    north=None,
    west=None,
    south=None,
    east=None,
    title=None,
    ax=None,
    save_path=None,
):
    """时间序列图：区域内平均随时间变化。返回 figure。"""
    ds, cleanup = _open_dataset(file_path)
    try:
        da = ds[variable]
        if north is not None:
            da = sel_area(da, north, west, south, east)
        tname = time_name(da)
        if tname is None:
            raise ValueError("该数据没有时间维度，无法绘制时间序列")
        series = _convert_units(da.mean(dim=[d for d in da.dims if d != tname], keep_attrs=True).load())
        times, values = series[tname].values, series.values
    finally:
        ds.close()
        cleanup()

    if ax is None:
        fig, ax = _new_ax(figsize=(9, 4.5))
    else:
        fig = ax.figure
    ax.plot(times, values, linewidth=2.0, color="#1E40AF")
    ax.fill_between(times, values, alpha=0.35, color="#1E40AF")
    ax.set_xlabel("时间", fontsize=11)
    ax.set_ylabel(_var_label(series), fontsize=11)
    ax.set_title(title or f"{var_cn_name(variable)} 区域平均时间序列",
                 fontsize=13, fontweight="bold", color="#0B223A")
    # 轴级旋转，避免 figure 级 autofmt_xdate 触发整图重排、与 tight_layout 冲突
    ax.tick_params(axis="x", rotation=30)
    ax.grid(True, axis="y", alpha=0.4, linestyle="--")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
    return fig


def plot_profile(
    file_path,
    variable,
    along="lat",
    section=None,
    north=None,
    west=None,
    south=None,
    east=None,
    cmap="viridis",
    title=None,
    ax=None,
    save_path=None,
):
    """垂直剖面图：气压层 ×（纬度或经度）截面。返回 figure。

    along='lat' 时固定经度（section 为经度值）沿纬度剖面；
    along='lon' 时固定纬度（section 为纬度值）沿经度剖面。
    """
    ds, cleanup = _open_dataset(file_path)
    try:
        da = ds[variable]
        if north is not None:
            da = sel_area(da, north, west, south, east)
        if "pressure_level" not in da.dims:
            raise ValueError("该数据没有气压层维度，无法绘制垂直剖面")
        lat, lon = lat_name(da), lon_name(da)
        fixed_dim = lon if along == "lat" else lat
        if fixed_dim is None:
            raise ValueError("数据缺少纬度/经度坐标，无法绘制剖面")
        if section is None:
            section = float(da[fixed_dim].values[len(da[fixed_dim]) // 2])
        da = da.sel({fixed_dim: section}, method="nearest")
        x_axis = lat if along == "lat" else lon  # 剖面走向轴
        if x_axis is None:
            raise ValueError("数据缺少剖面走向维（纬度/经度）")
        keep = {"pressure_level", x_axis}
        for dim in list(da.dims):
            if dim not in keep:
                da = da.mean(dim=dim, keep_attrs=True)
        da = _convert_units(da.load())
        x = da[x_axis].values
        xlabel = "纬度" if along == "lat" else "经度"
        plev = da.pressure_level.values
        data = da.values
        # contourf 要求坐标单调递增（matplotlib 官方文档）；ERA5 气压层常为递减存储
        if plev.size > 1 and plev[0] > plev[-1]:
            plev = plev[::-1]
            data = data[::-1, :]
    finally:
        ds.close()
        cleanup()

    if ax is None:
        fig, ax = _new_ax(figsize=(8, 5))
    else:
        fig = ax.figure
    vmin, vmax = _robust_range(data)
    if vmax > vmin:
        mesh = ax.contourf(x, plev, data, levels=np.linspace(vmin, vmax, 21), cmap=cmap)
    else:  # 全常数数据兜底
        mesh = ax.contourf(x, plev, data, levels=20, cmap=cmap)
    ax.set_yscale("log")
    ax.invert_yaxis()  # 气压坐标惯例：低层在下、高层在上
    cb = fig.colorbar(mesh, ax=ax, orientation="vertical", pad=0.02, shrink=0.9, aspect=30)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel("气压层 (hPa)", fontsize=11)
    ax.set_title(title or f"{var_cn_name(variable)} 垂直剖面（{fixed_dim} = {section:.2f}）",
                 fontsize=13, fontweight="bold", color="#0B223A")
    _add_left_label(ax, _var_label(da))  # 要素名放图像左侧
    _finalize_figure(fig)
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
    return fig
