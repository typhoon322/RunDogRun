"""
v2_final/strategy/ranker.py — v3.0 选股评分排名
===================================================
Score = 40%动量 + 30%低价偏好 + 20%成交量 + 10%板块加成
v3: 引入 sector_mapper 修复板块加成形同虚设的 bug
"""
import logging
import sys
import os
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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

    # v3: 用 code→sector 映射表修复板块加成 bug
    # 旧代码用个股名 name 查表 (永远命中默认值), 现在用股票代码通过 sector_mapper 查行业
    try:
        from portfolio.sector_mapper import lookup_sector
    except ImportError:
        lookup_sector = lambda code: "未知"

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

        # v3.0 综合评分：用 code→sector 查行业，再用行业查板块强度
        momentum_score = momentum * 0.4
        price_score = (1 / (price + 1)) * 30  # 低价偏好
        volume_score = min(2.0, volume / 1e7) * 0.20
        stock_sector = lookup_sector(code)
        sector_score = sector_map.get(stock_sector, 3) * 0.03

        score = round(momentum_score + price_score + volume_score + sector_score, 2)

        # v3 Lite: 拆分子因子 (0-100 归一化)
        # trend = 动量 + 板块强度 (趋势方向)
        # flow  = 成交量 (资金活跃度)
        # value = 低价偏好 (估值吸引力)
        trend_raw = round(momentum_score + sector_score, 2)    # max ≈ 0.4*momentum + 0.03*sector
        flow_raw = round(volume_score, 2)                      # max ≈ 2.0
        value_raw = round(price_score, 2)                      # max ≈ 30

        # 归一化到 0-100 (基于经验上界)
        trend = min(100, max(0, round(trend_raw / 5.0 * 100)))   # 假设 max trend_raw≈5
        flow = min(100, max(0, round(flow_raw / 2.0 * 100)))     # max flow_raw≈2
        value = min(100, max(0, round(value_raw / 30.0 * 100)))  # max value_raw≈30

        results.append({
            "code": code,
            "name": name,
            "price": round(price, 2),
            "momentum": round(momentum, 2),
            "volume": int(volume) if volume == volume else 0,
            "pe": round(pe, 1),
            "score": score,
            "trend": trend,
            "flow": flow,
            "value": value,
        })

    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    logger.info(f"排名: {len(ranked)} 候选 → Top {min(top_n, len(ranked))}")
    return ranked[:top_n]
