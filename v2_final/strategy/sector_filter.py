"""
v2_final/strategy/sector_filter.py — v2.4 行业过滤
======================================================
只保留涨幅前5的强行业
"""
import logging
from typing import Any

logger = logging.getLogger("v2.sector_filter")


def get_strong_sectors(sectors: list[dict], top_n: int = 5) -> list[str]:
    """
    提取涨幅前N强行业名称。

    Returns:
        ["半导体", "电池", ...]
    """
    if not sectors:
        return []

    ranked = sorted(sectors, key=lambda x: x.get("change_pct", 0), reverse=True)
    names = [s["name"] for s in ranked[:top_n]]
    logger.info(f"强行业: {names}")
    return names


def filter_stocks_by_sector(
    stocks: list[dict],
    strong_sectors: list[str],
    max_price: float = 60.0,
    min_momentum: float = 1.5,
) -> list[dict]:
    """
    行业 + 价格 + 动量 三重过滤。

    Args:
        stocks: 全市场个股
        strong_sectors: 强行业名称列表
        max_price: 最高价格 (小资金优化)
        min_momentum: 最低涨幅
    """
    if not strong_sectors:
        return []

    filtered = []
    for s in stocks:
        name = str(s.get("name", ""))
        code = str(s.get("code", ""))
        price = float(s.get("price", 0) or 0)
        momentum = float(s.get("change_pct", 0) or 0)

        if "ST" in name or "*" in name:
            continue
        if code.startswith(("8", "9", "4")):
            continue
        if price <= 0 or price > max_price:
            continue
        if momentum < min_momentum:
            continue

        filtered.append(s)

    logger.info(f"行业过滤: {len(stocks)} → {len(filtered)} "
                f"(强行业={len(strong_sectors)} 价格<{max_price} 动量>{min_momentum}%)")
    return filtered
