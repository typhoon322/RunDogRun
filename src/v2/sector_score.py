"""
sector_scorer.py — Layer 1: 板块5维评分系统 (v1.1)
===================================================
五大维度: Trend / Momentum / Money Flow / Breadth / Stability
范围: 0–10分
"""

import logging
from typing import Any

import config

logger = logging.getLogger("quant-collector.sector-scorer")


def score_sectors(
    sectors_today: list[dict[str, Any]],
    history: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """
    对每个板块计算5维评分。

    Args:
        sectors_today: 当日板块数据列表
        history: {sector_name: [历史数据, ...]} 按日期升序

    Returns:
        评分后的板块列表 (含各维度分数)
    """
    if history is None:
        history = {}

    results = []
    for sector in sectors_today:
        name = sector["name"]
        hist = history.get(name, [])

        trend = _score_trend(sector, hist)
        momentum = _score_momentum(sector, hist)
        money_flow = _score_money_flow(sector)
        breadth = _score_breadth(sector)
        stability = _score_stability(sector, hist)

        total = trend + momentum + money_flow + breadth + stability
        label = _classify_sector(total)

        results.append({
            "name": name,
            "code": sector.get("code", ""),
            "change_pct": sector.get("change_pct", 0),
            "trend": trend,
            "momentum": momentum,
            "money_flow": money_flow,
            "breadth": breadth,
            "stability": stability,
            "score": total,
            "label": label,
        })

    # 按总分降序排序，并标注 rank
    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


# ============================================================
# 五大维度评分函数
# ============================================================

def _score_trend(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Trend (0-2): 5日 + 20日趋势方向
    - 双周期上涨 → 2
    - 仅短期或震荡 → 1
    - 下跌 → 0
    """
    if len(history) >= 5:
        # 有足够历史: 5日累计涨跌 + 20日趋势
        recent_5 = history[-5:]
        cum_5d = sum(h.get("change_pct", 0) for h in recent_5)

        if len(history) >= 15:
            recent_20 = history[-20:]
            cum_20d = sum(h.get("change_pct", 0) for h in recent_20)
            if cum_5d > 0 and cum_20d > 0:
                return 2
            elif cum_5d > 0 or cum_20d > 0:
                return 1
            else:
                return 0
        else:
            return 2 if cum_5d > 0 else (1 if cum_5d > -1 else 0)
    else:
        # 降级: 单日
        chg = sector.get("change_pct", 0)
        if chg > 1:
            return 2
        elif chg > 0:
            return 1
        else:
            return 0


def _score_momentum(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Momentum (0-2): 3日 vs 10日涨跌加速度
    - 明显加速 (3日>10日) → 2
    - 持平或微增 → 1
    - 减速/负 → 0
    """
    if len(history) >= 10:
        recent_3 = history[-3:]
        recent_10 = history[-10:]
        cum_3 = sum(h.get("change_pct", 0) for h in recent_3)
        cum_10 = sum(h.get("change_pct", 0) for h in recent_10)
        recent_avg = cum_3 / 3 if len(recent_3) > 0 else 0
        long_avg = cum_10 / 10 if len(recent_10) > 0 else 0
        accel = recent_avg - long_avg

        if accel > 1.0:
            return 2
        elif accel > 0:
            return 1
        else:
            return 0
    elif len(history) >= 3:
        recent_3 = history[-3:]
        cum_3 = sum(h.get("change_pct", 0) for h in recent_3)
        if cum_3 > 2:
            return 2
        elif cum_3 > 0:
            return 1
        else:
            return 0
    else:
        # 降级: 用当日近似
        chg = sector.get("change_pct", 0)
        return 2 if chg > 2 else (1 if chg > 0 else 0)


def _score_money_flow(sector: dict[str, Any]) -> int:
    """
    Money Flow (0-2): 资金流向信号
    - strong_inflow → 2
    - positive → 1
    - neutral/negative → 0
    """
    mf = sector.get("money_flow", "neutral")
    if mf == "strong_inflow":
        return 2
    elif mf == "positive":
        return 1
    else:
        return 0


def _score_breadth(sector: dict[str, Any]) -> int:
    """
    Breadth (0-2): 板块宽度（上涨家数占比）
    - ≥70% → 2 (多股共振)
    - 40-70% → 1 (龙头驱动)
    - <40% → 0 (分化严重)
    """
    total = sector.get("total_stocks", 0)
    up = sector.get("up_count", 0)
    if total <= 0:
        return 1
    ratio = up / total
    if ratio >= config.BREADTH_HIGH:
        return 2
    elif ratio >= config.BREADTH_MEDIUM:
        return 1
    else:
        return 0


def _score_stability(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Stability (0-2): 波动稳定性
    - 低波动健康 → 2
    - 中等 → 1
    - 高波动/过热 → 0

    无历史 → 默认给 1
    """
    if len(history) < 5:
        return 1

    changes = [h.get("change_pct", 0) for h in history[-10:]]
    if len(changes) < 3:
        return 1

    mean = sum(changes) / len(changes)
    variance = sum((c - mean) ** 2 for c in changes) / len(changes)
    sigma = variance ** 0.5

    if sigma <= config.STABILITY_LOW_SIGMA:
        return 2
    elif sigma <= config.STABILITY_HIGH_SIGMA:
        return 1
    else:
        return 0


def _classify_sector(score: int) -> str:
    """板块分类"""
    if score >= config.SECTOR_SCORE_CORE_TREND:
        return "core_trend"
    elif score >= config.SECTOR_SCORE_QUALIFIED:
        return "rotation"
    elif score >= 4:
        return "watch"
    else:
        return "filter"
