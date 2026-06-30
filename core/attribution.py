"""
core/attribution.py — v2.6 策略收益归因系统
===============================================
两大维度: 个股贡献 + 行业贡献
回答: 到底为什么赚钱/亏钱?
"""
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger("v2.attribution")


def stock_attribution(
    portfolio: list[dict],
    price_data: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """
    个股收益归因: 每只股票的贡献 = 权重 × 期间收益
    """
    results = []
    for p in portfolio:
        code = p["code"]
        weight = p.get("weight", 0)
        prices = price_data.get(code, [])
        name = p.get("name", code)

        if len(prices) < 2:
            results.append({"code": code, "name": name, "weight": weight,
                            "return": 0, "contribution": 0})
            continue

        ret = (prices[-1] / prices[0] - 1) * 100
        contribution = ret * weight

        results.append({
            "code": code, "name": name,
            "weight": round(weight * 100, 1),
            "return": round(ret, 1),
            "contribution": round(contribution, 2),
        })

    ranked = sorted(results, key=lambda x: x["contribution"], reverse=True)
    if ranked:
        logger.info(f"个股归因: {len(ranked)} 只, Top={ranked[0]['name']} {ranked[0]['contribution']:+.1f}%")
    return ranked


def sector_attribution(
    portfolio: list[dict],
    price_data: dict[str, list[float]],
    sector_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    行业收益归因: 按行业聚合贡献
    """
    if sector_map is None:
        sector_map = {}

    sector_perf: dict[str, list[float]] = defaultdict(list)

    for p in portfolio:
        code = p["code"]
        weight = p.get("weight", 0)
        prices = price_data.get(code, [])

        if len(prices) < 2:
            continue

        ret = (prices[-1] / prices[0] - 1)
        sector = sector_map.get(code, "其他")
        sector_perf[sector].append(ret * weight)

    results = []
    total_ret = sum(sum(v) for v in sector_perf.values())

    for sector, contributions in sector_perf.items():
        avg_ret = sum(contributions) / len(contributions) if contributions else 0
        total_contrib = sum(contributions)
        share = round(total_contrib / total_ret * 100, 1) if total_ret != 0 else 0

        results.append({
            "sector": sector,
            "stocks": len(contributions),
            "avg_return": round(avg_ret * 100, 2),
            "total_contribution": round(total_contrib * 100, 2),
            "share_pct": share,
        })

    ranked = sorted(results, key=lambda x: x["total_contribution"], reverse=True)
    if ranked:
        logger.info(f"行业归因: {len(ranked)} 个行业, Top={ranked[0]['sector']}")
    return ranked


def time_segment_attribution(
    equity_curve: list[float],
    segments: list[tuple[str, int, int]] | None = None,
) -> list[dict]:
    """
    时间段拆分: 如最近7天/30天/60天/全部
    """
    if segments is None:
        segments = [
            ("最近7天", -7, -1), ("最近30天", -30, -1),
            ("最近90天", -90, -1), ("全部", 0, -1),
        ]

    results = []
    for label, start, end in segments:
        seg = equity_curve[start:end]
        if len(seg) < 2:
            results.append({"period": label, "return": 0, "days": len(seg)})
            continue
        ret = round((seg[-1] / seg[0] - 1) * 100, 1)
        results.append({"period": label, "return": ret, "days": len(seg)})

    return results
