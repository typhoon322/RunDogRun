"""
provider_factory.py — 数据源自动选择器
========================================
优先级: HTTP(腾讯/东财) > AkShare
自动降级: 主源失败 → 备用源
"""
import logging
from typing import Any

from src.data.provider.base import DataProvider
from src.data.provider.http_provider import HTTPProvider
from src.data.provider.akshare_provider import AKShareProvider

logger = logging.getLogger("quant.data.factory")

_provider_cache: DataProvider | None = None


def get_provider() -> DataProvider:
    """获取最佳可用数据源 (带缓存)"""
    global _provider_cache
    if _provider_cache is not None and _provider_cache.health_check():
        return _provider_cache

    # 优先 HTTP (零依赖, 海外可用)
    providers = [HTTPProvider(), AKShareProvider()]
    for p in providers:
        try:
            if p.health_check():
                _provider_cache = p
                logger.info(f"数据源: {p.name}")
                return p
        except Exception:
            continue

    # 全失败, 返回 HTTP stub
    logger.warning("所有数据源不可用, 使用 HTTP stub")
    _provider_cache = HTTPProvider()
    return _provider_cache


def reset_provider() -> None:
    """重置缓存 (强制重新检测)"""
    global _provider_cache
    _provider_cache = None
