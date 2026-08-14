"""下载速度记录：把每次下载的耗时与平均速度追加到 CSV，便于对比与优化。"""

import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["time", "dataset", "queue_sec", "transfer_sec", "total_sec", "size_mb", "avg_speed_mbps"]


def append_speed_record(
    dataset: str,
    queue_sec: float,
    transfer_sec: float,
    size_bytes: int,
    csv_path: Path | None = None,
) -> dict:
    """追加一条下载速度记录。

    csv_path 缺省时写入项目根目录的 speed_reports/下载速度记录.csv；
    应用内传用户输出目录，避免打包后 __file__ 指向临时解压目录。
    """
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "dataset": dataset,
        "queue_sec": round(queue_sec, 1),
        "transfer_sec": round(transfer_sec, 1),
        "total_sec": round(queue_sec + transfer_sec, 1),
        "size_mb": round(size_bytes / 1024 / 1024, 2),
        "avg_speed_mbps": round(size_bytes / transfer_sec / 1024 / 1024, 2) if transfer_sec > 0 else 0.0,
    }
    path = csv_path or (Path(__file__).resolve().parents[2] / "speed_reports" / "下载速度记录.csv")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not path.exists()
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(record)
    except OSError:
        pass  # 记录失败不影响下载本身
    return record
