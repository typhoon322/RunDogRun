"""
stock_scorer.py — Layer 2: 个股5维评分系统 (v1.2)
===================================================
五大维度: Trend / Relative Strength / Volume / Structure / Timing
范围: 0–10分
"""

import logging
from typing import Any

import config

logger = logging.getLogger("quant-collector.stock-scorer")


def score_stocks(
    stocks_today: list[dict[str, Any]],
    sector_scores: list[dict[str, Any]],
    history: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
) -> list[dict[str, Any]]:
    """
    对每只个股计算5维评分。

    Args:
        stocks_today: 当日个股数据
        sector_scores: Layer 1 产出的板块评分列表
        history: {sector_name: {stock_code: [历史数据]}} (可选)

    Returns:
        评分后的个股列表
    """
    if history is None:
        history = {}

    # 构建板块→评分快查
    sector_lookup = {s["name"]: s for s in sector_scores}

    results = []
    for stock in stocks_today:
        # 跳过停牌
        if stock.get("is_suspended"):
            continue

        code = stock.get("code", "")
        name = stock.get("name", "")
        sector_name = stock.get("sector", "")

        # 获取历史
        stock_hist = []
        if sector_name in history:
            stock_hist = history[sector_name].get(code, [])

        # Layer 2 归属板块的 Layer 1 数据
        sector_info = sector_lookup.get(sector_name, {})

        trend = _score_trend(stock, stock_hist)
        relative_strength = _score_relative_strength(stock, sector_info)
        volume = _score_volume(stock)
        structure = _score_structure(stock, stock_hist)
        timing = _score_timing(stock, sector_info)

        total = trend + relative_strength + volume + structure + timing
        label = _classify_stock(total, relative_strength)

        results.append({
            "code": code,
            "name": name,
            "sector": sector_name,
            "return": stock.get("return", 0),
            "volume_ratio": stock.get("volume_ratio", 0),
            "trend": trend,
            "relative_strength": relative_strength,
            "volume": volume,
            "structure": structure,
            "timing": timing,
            "score": total,
            "label": label,
            "sector_score": sector_info.get("score", 0),
            "sector_label": sector_info.get("label", ""),
        })

    # 按总分降序
    results.sort(key=lambda x: x["score"], reverse=True)

    # 板块内排序
    _rank_within_sector(results)

    return results


# ============================================================
# 五大维度评分
# ============================================================

def _score_trend(
    stock: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Trend (0-2): 是否在上涨趋势中
    - 涨+有趋势动量 → 2
    - 平或微涨 → 1
    - 下跌 → 0
    """
    ret = stock.get("return", 0)

    if len(history) >= 5:
        cum_5d = sum(h.get("return", 0) for h in history[-5:])
        if ret > 0 and cum_5d > 0:
            return 2
        elif ret > 0 or cum_5d > 0:
            return 1
        else:
            return 0

    # 降级: 单日
    if ret > 3:
        return 2
    elif ret > 0:
        return 1
    else:
        return 0


def _score_relative_strength(
    stock: dict[str, Any],
    sector_info: dict[str, Any],
) -> int:
    """
    Relative Strength (0-2) ⭐核心指标
    判断是否跑赢板块

    计算: stock.return - sector.change_pct
    """
    stock_return = stock.get("return", 0)
    sector_return = sector_info.get("change_pct", 0)

    if sector_return == 0:
        # 板块无数据 → 中性
        return 1

    rs = stock_return - sector_return

    if rs > config.RS_OUTPERFORM_PCT:
        return 2
    elif rs >= -config.RS_INLINE_PCT:
        return 1
    else:
        return 0


def _score_volume(stock: dict[str, Any]) -> int:
    """
    Volume (0-2): 量能质量
    - 放量上涨 (>1.5) → 2
    - 正常 (0.7-1.5) → 1
    - 缩量或异常 → 0
    """
    vol = stock.get("volume_ratio", 1.0)
    ret = stock.get("return", 0)

    if vol > config.VOLUME_BREAKOUT and ret > 0:
        return 2
    elif config.VOLUME_NORMAL_LOW <= vol <= config.VOLUME_NORMAL_HIGH:
        return 1
    elif vol > config.VOLUME_BREAKOUT and ret <= 0:
        return 0  # 放量下跌 → 危险
    else:
        return 0


def _score_structure(
    stock: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Structure (0-2): 价格结构健康度
    - 强势(涨+量比健康) → 2
    - 震荡 → 1
    - 破位(跌+高量比) → 0
    """
    ret = stock.get("return", 0)
    vol = stock.get("volume_ratio", 1.0)

    if len(history) >= 5:
        # 有历史: 看是否从低位反弹或持续强势
        recent_returns = [h.get("return", 0) for h in history[-5:]]
        up_days = sum(1 for r in recent_returns if r > 0)
        if ret > 1 and vol > 1 and up_days >= 3:
            return 2
        elif up_days >= 2:
            return 1
        else:
            return 0

    # 降级: 当日表现
    if ret > 2 and vol > 1:
        return 2
    elif ret > 0:
        return 1
    else:
        return 0


def _score_timing(
    stock: dict[str, Any],
    sector_info: dict[str, Any],
) -> int:
    """
    Timing (0-2): 板块周期内的相对时机
    - 板块得分高 + 个股回报适中 → 早期启动 → 2
    - 板块得分高 + 个股已大涨 → 后期 → 0
    - 中等 → 1
    """
    sector_score = sector_info.get("score", 0)
    stock_return = stock.get("return", 0)

    if sector_score < config.SECTOR_SCORE_QUALIFIED:
        return 0  # 板块都不够格

    # 板块强 + 个股尚未暴涨 → 早期
    if sector_score >= 7 and stock_return < 5:
        return 2
    elif sector_score >= 6:
        return 1
    else:
        return 0


def _classify_stock(score: int, rs: int) -> str:
    """个股分类标签"""
    if score >= config.STOCK_SCORE_LEADING and rs >= 2:
        return "leading_stock"
    elif score >= config.STOCK_SCORE_CANDIDATE:
        return "candidate"
    elif score >= 5:
        return "watch"
    else:
        return "filter"


def _rank_within_sector(results: list[dict[str, Any]]) -> None:
    """按板块分组，标出板块内排名"""
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for r in results:
        groups[r.get("sector", "未知")].append(r)

    for sector_name, stocks in groups.items():
        stocks.sort(key=lambda x: x["score"], reverse=True)
        for i, s in enumerate(stocks):
            s["rank_in_sector"] = i + 1
