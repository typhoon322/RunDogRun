"""
logger.py — 文件 + 控制台双写日志, API调用计数
"""
import os
import logging
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))

_logger = None
_api_call_counts = {"total": 0}


def get_logger(name: str = "quant") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger.getChild(name) if name != "quant" else _logger

    _logger = logging.getLogger("quant")
    _logger.setLevel(logging.INFO)

    # 控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                                       datefmt="%Y-%m-%d %H:%M:%S"))
    _logger.addHandler(ch)

    # 文件
    os.makedirs("logs", exist_ok=True)
    today = datetime.now(CN_TZ).strftime("%Y%m%d")
    fh = logging.FileHandler(f"logs/run_{today}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _logger.addHandler(fh)

    return _logger


def count_api(source: str) -> None:
    _api_call_counts["total"] += 1
    _api_call_counts[source] = _api_call_counts.get(source, 0) + 1


def api_summary() -> dict:
    return dict(_api_call_counts)


def setup_logging():
    """兼容旧接口"""
    return get_logger()
