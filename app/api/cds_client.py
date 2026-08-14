"""CDS API 封装：请求构造与下载队列。"""

import io
import logging
import os
import re
import shutil
import sys
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.downloader import parallel_download
from app.core.speedlog import append_speed_record


def normalize_times(text: str) -> list[str] | None:
    """把 '00,06,12,18' 或 '00:00,12:00' 规范为 ['00:00', ...]；空文本返回 None。"""
    if not text or not text.strip():
        return None
    parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
    out = []
    for p in parts:
        if ":" in p:
            out.append(p)
        else:
            hour = int(p)
            if not (0 <= hour <= 23):
                raise ValueError(f"小时数值非法: {p}")
            out.append(f"{hour:02d}:00")
    return out


def _parse_ymd(date_range: str) -> tuple[list[str], list[str], list[str]]:
    """把 'YYYY-MM-DD/YYYY-MM-DD' 日期范围解析为 (year, month, day) 三组列表。

    日统计（derived）数据集不使用 date 参数，而要求 year/month/day，
    并允许列表交叉组合；这里取范围内出现过的年/月/日集合。
    """
    import datetime

    start_txt, _, end_txt = date_range.partition("/")
    start = datetime.date.fromisoformat(start_txt.strip())
    end = datetime.date.fromisoformat(end_txt.strip())
    years, months, days = set(), set(), set()
    cur = start
    while cur <= end:
        years.add(cur.strftime("%Y"))
        months.add(cur.strftime("%m"))
        days.add(cur.strftime("%d"))
        cur += datetime.timedelta(days=1)
    return sorted(years), sorted(months), sorted(days)


def build_request(params, area, date_range, times, data_format, use_ymd=False) -> dict:
    """构造 CDS 请求字典。params 为 dict，area 为 [N,W,S,E] 或 None。

    use_ymd=True 时（日统计 derived 数据集）把日期范围转为 year/month/day，
    且不发送 time 参数（日聚合在服务端完成）。
    """
    req = dict(params or {})
    if area:
        req["area"] = area
    if date_range:
        if use_ymd:
            years, months, days = _parse_ymd(date_range)
            req["year"] = years
            req["month"] = months
            req["day"] = days
        else:
            req["date"] = date_range
    if times and not use_ymd:
        req["time"] = times
    if data_format:
        req["data_format"] = data_format
    return req


def _is_license_error(exc: Exception) -> bool:
    """判断是否为"数据集使用条款未同意"错误（CDS 返回 403）。"""
    text = str(exc).lower()
    return "licence" in text and "403" in text


def _ensure_data_file(target: str) -> None:
    """CDS-DSS 平台对部分数据集（如 ERA5-Land）以 ZIP 打包交付数据文件，
    裸下载会把 zip 字节原样存成 .nc 导致无法读取。
    检测到 zip 魔数时，解压出其中的 netCDF/GRIB 文件并替换目标路径。
    """
    target = str(target)
    try:
        with open(target, "rb") as f:
            magic = f.read(4)
    except OSError:
        return
    if magic != b"PK\x03\x04":
        return  # 已是 netCDF/GRIB 等正常格式
    with zipfile.ZipFile(target) as zf:
        candidates = [
            n for n in zf.namelist()
            if n.lower().endswith((".nc", ".grib", ".grb", ".grib2"))
        ]
        if not candidates:
            raise ValueError("下载的压缩包内未找到 netCDF/GRIB 数据文件")
        tmp = target + ".extracted"
        with zf.open(candidates[0]) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
    os.replace(tmp, target)


def _error_advice(exc: Exception) -> str | None:
    """针对常见 CDS 下载错误给出中文处理建议（供日志输出）。"""
    text = str(exc)
    low = text.lower()
    if "none of the data you have requested is available yet" in low:
        m = re.search(r"latest date available[^:：]*[:：]\s*(\d{4}-\d{2}-\d{2})", text)
        latest = f"该数据集最新可用日期为 {m.group(1)}" if m else "该数据集最新可用日期早于请求的结束日期"
        return (
            f"{latest}。再分析数据发布通常滞后数天，"
            "请把下载的结束日期改到该日期之前，再重新添加任务。"
        )
    if "licence" in low and "403" in low:
        return "请在 CDS 网页登录并同意该数据集的使用条款后再试。"
    return None


@dataclass
class DownloadTask:
    dataset: str
    request: dict
    target: str
    description: str
    status: str = "排队中"
    cancelled: bool = False
    task_id: int = 0


class _OutputCapture(threading.Thread):
    """读取子输出流，把进度百分比与普通文本分发给信号。"""

    def __init__(self, stream, log_emit, progress_emit):
        super().__init__(daemon=True)
        self._stream = stream
        self._log = log_emit
        self._progress = progress_emit
        self._buf = ""

    def run(self):
        while True:
            chunk = self._stream.read(1024)
            if not chunk:
                break
            self._buf += chunk
            while "\r" in self._buf or "\n" in self._buf:
                seg, sep, rest = self._buf.partition("\r")
                if not sep:
                    seg, sep, rest = self._buf.partition("\n")
                self._buf = rest
                seg = seg.strip()
                if not seg:
                    continue
                m = re.search(r"(\d{1,3})\s*%", seg)
                if m:
                    self._progress(int(m.group(1)))
                else:
                    self._log(seg)


class DownloadWorker(QThread):
    """串行执行下载队列的后台线程。"""

    log_message = Signal(str)
    task_status = Signal(int, str)   # (task_id, status)
    task_progress = Signal(int, int)  # (task_id, percent)，-1 表示不确定
    license_error = Signal(str, str)  # (dataset, message)：数据集条款未同意

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[DownloadTask] = []
        self._next_id = 1
        self._current: DownloadTask | None = None
        self._alive = False
        self._stop = False

    def add_task(self, dataset, request, target, description) -> int:
        task = DownloadTask(dataset, request, target, description, task_id=self._next_id)
        self._next_id += 1
        self._tasks.append(task)
        if not self._alive:
            self._alive = True
            if not self.isFinished():
                self.wait()          # 线程正在退场：等它完全结束再重启（窗口极短，无任务在处理）
            self.start()
        return task.task_id

    def cancel_task(self, task_id) -> None:
        for t in self._tasks:
            if t.task_id == task_id:
                t.cancelled = True
                self.log_message.emit(f"[{task_id}] 已标记取消（排队任务将跳过）")
                return
        cur = self._current
        if cur is not None and cur.task_id == task_id:
            self.log_message.emit(f"[{task_id}] 正在下载中，无法中断，请等待完成")
            return
        self.log_message.emit(f"[{task_id}] 任务不存在或已完成，无需取消")

    def stop(self):
        """停止队列：取消所有排队任务；当前任务结束后线程退出。"""
        for t in self._tasks:
            t.cancelled = True
        self._stop = True

    def has_pending(self) -> bool:
        """是否有未完成的任务（正在下载或仍在队列中）。"""
        return self._current is not None or bool(self._tasks)

    def run(self):
        try:
            while self._tasks and not self._stop:
                task = self._tasks.pop(0)
                self._current = task
                if task.cancelled:
                    task.status = "已取消"
                    self.task_status.emit(task.task_id, task.status)
                    continue
                task.status = "下载中"
                self.task_status.emit(task.task_id, task.status)
                try:
                    self._download(task)
                    if task.cancelled:
                        task.status = "已取消"
                    else:
                        task.status = "完成"
                    self.task_status.emit(task.task_id, task.status)
                except Exception as exc:  # noqa: BLE001 - 单任务失败不中断队列
                    task.status = "已取消" if task.cancelled else "失败"
                    if task.status == "失败":
                        msg = str(exc)
                        self.log_message.emit(f"[{task.task_id}] 失败：{msg}")
                        if _is_license_error(exc):
                            self.license_error.emit(task.dataset, msg)
                        else:
                            advice = _error_advice(exc)
                            if advice:
                                self.log_message.emit(f"[{task.task_id}] 建议：{advice}")
                    self._cleanup_partial(task)
                    self.task_status.emit(task.task_id, task.status)
                finally:
                    self._current = None
        finally:
            self._alive = False

    def _download(self, task):
        try:
            import cdsapi
        except ImportError:
            raise RuntimeError(
                "缺少 cdsapi 库：当前安装/打包的版本未包含下载模块。"
                "请在本机执行 `pip install cdsapi` 后重新打包，或更新应用版本。"
            )

        handler = _LogHandler(lambda msg: self.log_message.emit(f"[{task.task_id}] {msg}"))
        loggers = [logging.getLogger("cdsapi"), logging.getLogger("ecmwf.datastores.legacy_client")]
        old_levels = [lg.level for lg in loggers]
        for lg in loggers:
            lg.addHandler(handler)
            lg.setLevel(logging.INFO)

        real_stdout, real_stderr = sys.stdout, sys.stderr
        read_fd, write_fd = os.pipe()
        out_writer = os.fdopen(write_fd, "w", encoding="utf-8", errors="replace")
        err_writer = os.fdopen(os.dup(write_fd), "w", encoding="utf-8", errors="replace")
        capture = _OutputCapture(
            os.fdopen(read_fd, "r", encoding="utf-8", errors="replace"),
            lambda msg: self.log_message.emit(f"[{task.task_id}] {msg}"),
            lambda pct: self.task_progress.emit(task.task_id, pct),
        )
        capture.start()
        sys.stdout = out_writer
        sys.stderr = err_writer
        try:
            self.log_message.emit(f"[{task.task_id}] 提交请求：{task.dataset} {task.description}")
            client = cdsapi.Client()
            t_queue0 = time.monotonic()
            result = client.retrieve(task.dataset, task.request)  # 含服务端排队等待
            t_queue1 = time.monotonic()
            queue_sec = t_queue1 - t_queue0
            self.task_progress.emit(task.task_id, -1)  # 传输阶段：先不确定进度
            t_xfer0 = time.monotonic()
            url = getattr(result, "location", None)
            size = getattr(result, "content_length", None)
            if url:
                # 并行 Range 分片下载（单流限速时可提升数倍），异常时回退官方下载
                try:
                    parallel_download(
                        url,
                        task.target,
                        size=size,
                        progress_cb=lambda done, total: self.task_progress.emit(
                            task.task_id, int(done * 100 / total) if total else -1
                        ),
                    )
                except Exception:
                    self._download_official(result, task)
            else:
                self._download_official(result, task)
            _ensure_data_file(task.target)
            t_xfer1 = time.monotonic()
            transfer_sec = t_xfer1 - t_xfer0
            size = os.path.getsize(task.target)
            speed = size / transfer_sec if transfer_sec > 0 else 0.0
            self.log_message.emit(
                f"[{task.task_id}] 已保存：{task.target}"
                f"（{size / 1024 / 1024:.1f} MB，服务端排队 {queue_sec:.0f}s + "
                f"传输 {transfer_sec:.0f}s，平均 {speed / 1024 / 1024:.2f} MB/s）"
            )
            append_speed_record(
                task.dataset, queue_sec, transfer_sec, size,
                Path(task.target).parent / "下载速度记录.csv",
            )
        finally:
            sys.stdout = real_stdout
            sys.stderr = real_stderr
            out_writer.close()
            err_writer.close()
            capture.join(timeout=2)
            for lg, lv in zip(loggers, old_levels):
                lg.removeHandler(handler)
                lg.setLevel(lv)

    def _download_official(self, result, task):
        """回退路径：使用 cdsapi 官方下载（支持断点续传与内置重试）。"""
        self.log_message.emit(f"[{task.task_id}] 并行下载不可用，改用官方下载通道…")
        result.download(task.target)

    def _cleanup_partial(self, task):
        try:
            if os.path.exists(task.target):
                os.remove(task.target)
        except OSError:
            pass


class _LogHandler(logging.Handler):
    """把 cdsapi 日志转发为界面日志。"""

    def __init__(self, emit_fn):
        super().__init__()
        self._emit = emit_fn

    def emit(self, record):
        try:
            self._emit(record.getMessage())
        except Exception:  # noqa: BLE001
            pass
