"""配置管理：.cdsapirc 读写、用户自定义模板。"""

import json
from pathlib import Path

DEFAULT_URL = "https://cds.climate.copernicus.eu/api"
DEFAULT_KEY = ""  # 不内置密钥，请用户在“设置”页填写自己的 CDS API Key


def cdsapirc_path() -> Path:
    return Path.home() / ".cdsapirc"


def read_cdsapirc(path: Path | None = None) -> dict:
    """读取 .cdsapirc，返回 {"url":..., "key":...}；文件缺失或格式非法返回 {}。"""
    p = path or cdsapirc_path()
    if not p.exists():
        return {}
    result = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


def write_cdsapirc(url: str, key: str, path: Path | None = None) -> None:
    """写入 .cdsapirc（自动创建父目录）。"""
    p = path or cdsapirc_path()
    p.write_text(f"url: {url.strip()}\nkey: {key.strip()}\n", encoding="utf-8")


def is_cdsapirc_valid(path: Path | None = None) -> bool:
    cfg = read_cdsapirc(path)
    return bool(cfg.get("url") and cfg.get("key"))


TEMPLATES_FILE = Path.home() / ".era5_downloader" / "templates.json"


def load_user_templates(path: Path | None = None) -> dict:
    """读取用户自定义模板 {名称: {"dataset": str, "params": dict}}；缺失/损坏返回 {}。"""
    p = path or TEMPLATES_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_templates(templates: dict, path: Path | None = None) -> None:
    """保存用户自定义模板，自动创建父目录。"""
    p = path or TEMPLATES_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding="utf-8")
