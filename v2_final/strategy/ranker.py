"""
v2_final/strategy/ranker.py — v2.3 选股评分排名
===================================================
Score = 40%动量 + 30%低价偏好 + 20%成交量 + 10%板块加成
"""
import logging
from typing import Any

logger = logging.getLogger("v2.ranker")


def rank_stocks(stocks: list[dict], sector_rank: list[dict] | None = None,
                top_n: int = 20, min_momentum: float = 1.5) -> list[dict[str, Any]]:
    """
    全市场评分排序。

    条件: 非ST + PE>0 + 动量>1.5% + 价格>0
    评分: 动量×0.4 + 低价×0.3 + 量×0.2 + 板块×0.1
    """
    # 板块快查
    sector_map = {}
    if sector_rank:
        sector_map = {s["name"]: s.get("strength", 0) for s in sector_rank}

    results = []
    for s in stocks:
        name = str(s.get("name", ""))
        code = str(s.get("code", ""))
        momentum = float(s.get("change_pct", 0) or 0)
        volume = float(s.get("volume", 0) or 0)
        price = float(s.get("price", 0) or 0)
        pe = float(s.get("pe", 0) or 0)

        # 基础过滤
        if "ST" in name or "*" in name or "N" in name:
            continue
        if code.startswith(("8", "9", "4")):  # 北交所/科创板/新股
            continue
        if pe <= 0 or price <= 0:
            continue
        if momentum < min_momentum:
            continue
        if volume < 5e5:
            continue

        # v2.3 综合评分
        momentum_score = momentum * 0.4
        price_score = (1 / (price + 1)) * 30  # 低价偏好
        volume_score = min(2.0, volume / 1e7) * 0.20
        sector_score = sector_map.get(name, 3) * 0.03

        score = round(momentum_score + price_score + volume_score + sector_score, 2)

        results.append({
            "code": code,
            "name": name,
            "price": round(price, 2),
            "momentum": round(momentum, 2),
            "volume": int(volume) if volume == volume else 0,  # NaN safe
            "pe": round(pe, 1),
            "score": score,
        })

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    logger.info(f"排名: {len(ranked)} 候选 → Top {min(top_n, len(ranked))}")
    return ranked[:top_n]
