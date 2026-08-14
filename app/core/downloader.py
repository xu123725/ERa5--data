"""并行分片下载器。

利用 HTTP Range 并发拉取文件。对 CDS 这类"单流限速、但支持 Range"的对象存储，
可显著提升传输速度（实测 CDS 单流约 30-46 kB/s，而本机带宽约 1.76 MB/s）。
服务端不支持 Range 时自动回退为单流下载。
"""

import os
import threading
from pathlib import Path

import requests

DEFAULT_STREAMS = 8
DEFAULT_CHUNK = 256 * 1024
MAX_RETRIES = 3


class RangeUnsupported(Exception):
    """服务端忽略 Range 请求，无法并行下载。"""


def _head_size(url: str, timeout: int = 30) -> int:
    r = requests.head(url, timeout=timeout)
    r.raise_for_status()
    size = int(r.headers.get("content-length") or 0)
    if size <= 0:
        raise ValueError("无法获取文件大小（缺少 Content-Length）")
    return size


def _split_ranges(size: int, streams: int) -> list[tuple[int, int]]:
    """把 [0, size) 切成 streams 段，返回闭区间 [start, end] 列表。"""
    ranges: list[tuple[int, int]] = []
    start = 0
    for i in range(streams):
        end = start + size // streams - 1 if i < streams - 1 else size - 1
        ranges.append((start, end))
        start = end + 1
    return ranges


def _download_part(url, start, end, path, chunk, stop_event, shared, errors):
    """下载 [start, end] 字节范围写入 path 对应偏移；失败自动重试。"""
    for attempt in range(MAX_RETRIES):
        if stop_event.is_set():
            return
        try:
            headers = {"Range": f"bytes={start}-{end}"}
            with requests.get(url, headers=headers, stream=True, timeout=300) as r:
                if r.status_code == 200:  # 服务端忽略 Range
                    errors.append(RangeUnsupported("服务端未响应 Range，回退单流下载"))
                    stop_event.set()
                    return
                r.raise_for_status()
                with open(path, "r+b") as fh:
                    fh.seek(start)
                    for data in r.iter_content(chunk):
                        if stop_event.is_set():
                            return
                        fh.write(data)
                        with shared["lock"]:
                            shared["total"] += len(data)
                            done = shared["total"]
                        cb = shared.get("progress_cb")
                        if cb:
                            cb(done, shared["size"])
            return
        except Exception as exc:  # noqa: BLE001 - 重试耗尽后上报
            if attempt == MAX_RETRIES - 1:
                errors.append(exc)
                stop_event.set()
                return
            stop_event.wait(2**attempt)


def _single_stream(url, target, chunk, progress_cb, size=None):
    """单流整文件下载（回退路径）。"""
    tmp = target + ".part"
    total = 0
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for data in r.iter_content(chunk):
                f.write(data)
                total += len(data)
                if progress_cb and size:
                    progress_cb(total, size)
    os.replace(tmp, target)
    return target


def _cleanup(path):
    try:
        os.remove(path)
    except OSError:
        pass


def parallel_download(
    url: str,
    target: str,
    size: int | None = None,
    streams: int = DEFAULT_STREAMS,
    chunk: int = DEFAULT_CHUNK,
    progress_cb=None,
    timeout: int = 30,
) -> str:
    """并行分片下载到 target，返回 target 路径。

    - size 未知时先 HEAD 获取；获取失败或文件小于 1MB 走单流。
    - 任一分片返回 200（不支持 Range）时回退单流。
    - 分片重试耗尽后抛异常。
    progress_cb(已下载字节数, 总字节数) 可空。
    """
    target = str(target)
    try:
        if size is None:
            size = _head_size(url, timeout)
    except Exception:  # noqa: BLE001 - HEAD 失败走单流兜底
        return _single_stream(url, target, chunk, progress_cb, None)

    if size < 1024 * 1024:  # 小文件分片开销大于收益
        return _single_stream(url, target, chunk, progress_cb, size)

    streams = max(1, min(streams, size // (512 * 1024)))
    tmp = target + ".part"
    with open(tmp, "wb") as f:
        f.truncate(size)

    shared = {"total": 0, "lock": threading.Lock(), "size": size, "progress_cb": progress_cb}
    stop = threading.Event()
    errors: list[Exception] = []

    threads = []
    for start, end in _split_ranges(size, streams):
        t = threading.Thread(
            target=_download_part, args=(url, start, end, tmp, chunk, stop, shared, errors), daemon=True
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    if errors:
        _cleanup(tmp)
        if isinstance(errors[0], RangeUnsupported):
            return _single_stream(url, target, chunk, progress_cb, size)
        raise errors[0]

    actual = os.path.getsize(tmp)
    if actual != size:
        _cleanup(tmp)
        raise RuntimeError(f"下载不完整：期望 {size} 字节，实际 {actual} 字节")
    os.replace(tmp, target)
    if progress_cb:
        progress_cb(size, size)
    return target
