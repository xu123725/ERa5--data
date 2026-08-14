"""数据处理：合并 / 裁剪 / 转 CSV。"""

import os
import shutil
import tempfile

import xarray as xr


def _non_ascii_path(path) -> bool:
    """路径是否含非 ASCII 字符。

    Windows 上 netCDF4 底层库无法打开/写入中文路径的 .nc 文件（实测
    FileNotFoundError）。此类路径改用"复制到 ASCII 临时文件"的方式读写，
    完成后移回原路径，绕开 netCDF4 的路径限制。
    """
    return any(ord(c) > 127 for c in str(path))


def _ascii_temp_copy(src) -> str:
    """把文件复制到 ASCII 临时路径，返回临时路径。"""
    fd, tmp = tempfile.mkstemp(suffix=".nc")
    os.close(fd)
    try:
        shutil.copyfile(str(src), tmp)
    except Exception:
        _try_remove(tmp)
        raise
    return tmp


def _try_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _open_dataset(path, **kwargs):
    """打开数据集，返回 (dataset, 清理函数)。

    中文路径时先复制到 ASCII 临时文件；调用方须在 finally 中
    ``ds.close(); cleanup()`` 以释放并删除临时副本。
    """
    if not _non_ascii_path(path):
        return xr.open_dataset(path, **kwargs), (lambda: None)
    tmp = _ascii_temp_copy(path)
    try:
        ds = xr.open_dataset(tmp, **kwargs)
    except Exception:
        _try_remove(tmp)
        raise
    return ds, (lambda: _try_remove(tmp))


def _save_netcdf(dataset, path, **kwargs):
    if not _non_ascii_path(path):
        dataset.to_netcdf(path, **kwargs)
        return
    fd, tmp = tempfile.mkstemp(suffix=".nc")
    os.close(fd)
    try:
        dataset.to_netcdf(tmp, **kwargs)
        shutil.move(tmp, str(path))
    except Exception:
        _try_remove(tmp)
        raise


# ---------- 维度名兼容 ----------
# 旧 CDS 下载：time / lat / lon；新 CDS-DSS 下载：valid_time / latitude / longitude

def lat_name(da) -> str | None:
    for name in ("latitude", "lat"):
        if name in da.dims:
            return name
    return None


def lon_name(da) -> str | None:
    for name in ("longitude", "lon"):
        if name in da.dims:
            return name
    return None


def time_name(da) -> str | None:
    for name in ("valid_time", "time"):
        if name in da.dims:
            return name
    return None


def sel_area(da, north, west, south, east):
    """按经纬度范围裁剪，兼容新旧坐标命名与纬度/经度递增/递减顺序。"""
    lat = lat_name(da)
    lon = lon_name(da)
    if lat is None or lon is None:
        raise ValueError("数据缺少纬度/经度坐标")
    if da[lat].size > 1 and da[lat].values[0] > da[lat].values[-1]:
        south, north = north, south
    if da[lon].size > 1 and da[lon].values[0] > da[lon].values[-1]:
        west, east = east, west
    return da.sel({lat: slice(south, north), lon: slice(west, east)})


# ---------- 功能 ----------

def merge_netcdf(file_paths: list[str], output_path: str) -> None:
    """按坐标合并多个 netCDF 文件（不依赖 dask）。"""
    if not file_paths:
        raise ValueError("请至少选择一个文件")
    pairs = [_open_dataset(p) for p in file_paths]
    datasets = [ds for ds, _ in pairs]
    try:
        merged = xr.combine_by_coords(datasets, combine_attrs="drop_conflicts")
        _save_netcdf(merged, output_path)
    finally:
        for ds in datasets:
            ds.close()
        for _, cleanup in pairs:
            cleanup()


def crop_netcdf(input_path, north, west, south, east, output_path) -> None:
    """按经纬度范围裁剪（北/西/南/东）。"""
    ds, cleanup = _open_dataset(input_path)
    try:
        ds = sel_area(ds, north, west, south, east)
        if ds[lat_name(ds)].size == 0 or ds[lon_name(ds)].size == 0:
            raise ValueError("裁剪范围内无数据，请检查经纬度范围")
        _save_netcdf(ds, output_path)
    finally:
        ds.close()
        cleanup()


def netcdf_to_csv(input_path, variable, output_path, start_time=None, end_time=None) -> None:
    """导出指定变量为 CSV；start_time/end_time 为 'YYYY-MM-DD' 字符串，可省略。"""
    ds, cleanup = _open_dataset(input_path)
    try:
        if variable not in ds:
            raise ValueError(f"数据集中不存在变量: {variable}")
        data = ds[variable]
        if start_time:
            tname = time_name(data)
            if tname is None:
                raise ValueError("数据没有时间维度，无法按时间筛选")
            data = data.sel({tname: slice(start_time, end_time)})
        data.to_dataframe().dropna().to_csv(output_path)
    finally:
        ds.close()
        cleanup()