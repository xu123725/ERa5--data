"""ERA5 下载速度测试脚本。

真实发起一次 ERA5 请求，记录各阶段耗时与平均下载速度，
结果写入 speed_reports/ 目录（JSON 报告 + CSV 历史记录）。

用法：
    py -3 scripts/speed_test.py [--dataset reanalysis-era5-single-levels]
                                [--days 7] [--hours all] [--area china] [--repeat 1]
"""

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# 允许直接以脚本方式运行（scripts/ 下运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import cdsapirc_path, is_cdsapirc_valid  # noqa: E402
from app.core.speedlog import append_speed_record  # noqa: E402

REPORT_DIR = Path(__file__).resolve().parent.parent / "speed_reports"
CHINA_AREA = [54, 73, 18, 135]


def build_request(days: int, hours, area: str) -> dict:
    """构造测试请求。days 天 × hours 个时次 × area 区域，体积可调。"""
    start = date(2024, 1, 1)
    end = start + timedelta(days=days - 1)
    req = {
        "product_type": "reanalysis",
        "variable": "2m_temperature",
        "date": f"{start}/{end}",
        "time": [f"{h:02d}:00" for h in hours],
        "data_format": "netcdf",
    }
    if area == "china":
        req["area"] = CHINA_AREA
    return req


def fmt_mb(n: float) -> str:
    return f"{n / 1024 / 1024:.2f} MB"


def main() -> int:
    parser = argparse.ArgumentParser(description="ERA5 下载速度测试")
    parser.add_argument("--dataset", default="reanalysis-era5-single-levels", help="数据集名称")
    parser.add_argument("--days", type=int, default=7, help="时间跨度天数（默认 7）")
    parser.add_argument("--hours", default="all", help="时次，如 all / 0,6,12,18（默认 all=24 个）")
    parser.add_argument("--area", default="china", choices=["china", "global"], help="区域（默认 china）")
    parser.add_argument("--repeat", type=int, default=1, help="重复测试次数")
    parser.add_argument("--parallel", action="store_true", default=True, help="使用并行分片下载（默认开启）")
    parser.add_argument("--no-parallel", dest="parallel", action="store_false", help="使用官方单流下载")
    parser.add_argument("--streams", type=int, default=8, help="并行分片数（默认 8）")
    args = parser.parse_args()

    if not is_cdsapirc_valid():
        print(f"[错误] 未检测到有效配置：{cdsapirc_path()}")
        print("请先在程序“设置”页保存 API 配置。")
        return 1

    import cdsapi

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    client = cdsapi.Client()

    for i in range(args.repeat):
        hours = list(range(24)) if args.hours == "all" else [int(h) for h in args.hours.split(",")]
        request = build_request(args.days, hours, args.area)
        target = REPORT_DIR / f"speed_test_{datetime.now():%Y%m%d_%H%M%S}_{i}.nc"
        print(f"\n===== 测试 {i + 1}/{args.repeat} =====")
        print(f"数据集: {args.dataset}（{args.days} 天 × {len(hours)} 时次 × {args.area}）")
        print(f"请求:   {json.dumps(request, ensure_ascii=False)}")

        t0 = time.monotonic()
        print("[1/3] 提交请求并等待服务端处理（排队中，可能需数分钟）...")
        try:
            result = client.retrieve(args.dataset, request)
        except Exception as exc:  # noqa: BLE001 - 测试脚本需要捕获任意失败
            print(f"[错误] 请求提交失败：{exc}")
            print("若为 403，请先在 CDS 网页（cds.climate.copernicus.eu）登录并同意该数据集的使用条款。")
            return 1
        t1 = time.monotonic()
        queue_sec = t1 - t0

        print(f"[2/3] 服务端已就绪（排队耗时 {queue_sec:.1f}s），开始下载...")
        try:
            if args.parallel:
                from app.core.downloader import parallel_download

                url = getattr(result, "location", None)
                size = getattr(result, "content_length", None)
                if url:
                    parallel_download(url, str(target), size=size, streams=args.streams)
                else:
                    result.download(str(target))
            else:
                result.download(str(target))
        except Exception as exc:  # noqa: BLE001
            print(f"[错误] 下载失败：{exc}")
            if target.exists():
                target.unlink()
            return 1
        t2 = time.monotonic()
        transfer_sec = t2 - t1

        size = target.stat().st_size
        speed = size / transfer_sec if transfer_sec > 0 else 0.0

        print(f"[3/3] 完成：{fmt_mb(size)}，下载耗时 {transfer_sec:.1f}s，"
              f"平均速度 {speed / 1024 / 1024:.2f} MB/s，总耗时 {t2 - t0:.1f}s")

        # CSV 历史记录（与程序内下载共用同一模块）
        record = append_speed_record(args.dataset, queue_sec, transfer_sec, size, REPORT_DIR / "下载速度记录.csv")
        print(f"历史记录已追加: {REPORT_DIR / '下载速度记录.csv'}")

        # JSON 报告
        record["request"] = request
        json_path = REPORT_DIR / f"speed_test_{datetime.now():%Y%m%d_%H%M%S}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已保存: {json_path}")

    print("\n测试完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
