"""
signals.py — v1.3 买卖信号检测引擎
=====================================
3种买入信号 (A/B/C) + 3种卖出信号 (D/E/F)

依赖: 历史价格数据(读取data/*.json) 计算 MA/前高/量比
"""

import logging
from collections import defaultdict
from typing import Any

import config

logger = logging.getLogger("quant-collector.signals")


def compute_indicators(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    price_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    为单只股票计算技术指标。

    Returns:
        {ma10, ma20, prev_high_5d, avg_vol_5d, above_ma20, above_ma10,
         vol_trend, enough_history}
    """
    if price_history is None:
        price_history = []

    prices = [h.get("price", 0) for h in price_history if h.get("price", 0) > 0]
    highs = [h.get("high", 0) for h in price_history if h.get("high", 0) > 0]
    vols = [h.get("volume_ratio", 1.0) for h in price_history]

    # 加入当日数据
    cur_price = stock.get("price", 0)
    cur_high = stock.get("high", 0)
    if cur_price > 0:
        prices.append(cur_price)
    if cur_high > 0:
        highs.append(cur_high)

    enough = len(prices) >= 5

    # 均线
    ma20 = sum(prices[-20:]) / min(20, len(prices)) if prices and len(prices) >= 5 else cur_price
    ma10 = sum(prices[-10:]) / min(10, len(prices)) if prices and len(prices) >= 5 else cur_price

    # 前高
    prev_high_5d = max(highs[-6:-1]) if len(highs) >= 6 else cur_high

    # 5日均量比
    avg_vol_5d = sum(vols[-6:-1]) / max(1, len(vols[-6:-1])) if len(vols) >= 6 else 1.0

    cur_vol = stock.get("volume_ratio", 1.0)

    return {
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "prev_high_5d": round(prev_high_5d, 2),
        "avg_vol_5d": round(avg_vol_5d, 2),
        "above_ma20": cur_price >= ma20 * 0.98,  # 2%容差
        "above_ma10": cur_price >= ma10 * 0.98,
        "vol_trend": "up" if cur_vol > avg_vol_5d else ("down" if cur_vol < avg_vol_5d else "flat"),
        "enough_history": enough,
    }


# ============================================================
# 买入信号
# ============================================================

def detect_entry_breakout(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    indicators: dict[str, Any],
) -> dict[str, Any] | None:
    """
    A类: 突破买入

    条件: 板块≥6 + 个股≥7 + 价>5日高 + 量≥1.5x
    """
    sector_score = sector_scored.get("score", 0)
    stock_score = stock.get("score", 0)
    price = stock.get("price", 0)
    prev_high = indicators.get("prev_high_5d", 0)
    vol_ratio = stock.get("volume_ratio", 0)

    if sector_score < config.SIGNAL_SECTOR_UPGRADE_MIN:
        return None
    if stock_score < config.STOCK_SCORE_CANDIDATE:
        return None
    if price <= prev_high * 0.99:  # 1%容差
        return None
    if vol_ratio < config.SIGNAL_BREAKOUT_VOL_RATIO:
        return None

    # 分级: A+ (板块个股共振) vs A (单股) vs B (勉强)
    if sector_score >= config.SECTOR_SCORE_CORE_TREND and stock.get("return", 0) > 2:
        grade = "A+"
        confidence = 0.85
    elif stock.get("return", 0) > 0 and vol_ratio >= 1.5:
        grade = "A"
        confidence = 0.75
    elif not indicators.get("enough_history", False):
        grade = "B"
        confidence = 0.55
    else:
        grade = "B"
        confidence = 0.60

    return {
        "signal_type": "breakout",
        "signal_grade": grade,
        "action": "BUY",
        "confidence": confidence,
        "reason": (
            f"突破买入: 价{price}>{prev_high:.2f}(前高), "
            f"量比{vol_ratio:.1f}, 板块{sector_score}分"
        ),
    }


def detect_entry_pullback(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    indicators: dict[str, Any],
) -> dict[str, Any] | None:
    """
    B类: 回踩买入

    条件: 价>MA20 + 缩量 + 板块≥6 + 个股≥6
    """
    sector_score = sector_scored.get("score", 0)
    stock_score = stock.get("score", 0)
    vol_ratio = stock.get("volume_ratio", 0)
    ret = stock.get("return", 0)

    if sector_score < config.SIGNAL_SECTOR_UPGRADE_MIN:
        return None
    if stock_score < config.STOCK_SCORE_CANDIDATE - 1:  # 放宽到6
        return None
    if not indicators.get("above_ma20", False):
        return None
    # 缩量: 量比 < 0.9
    if vol_ratio > config.SIGNAL_PULLBACK_VOL_MAX:
        return None

    confidence = 0.65 if indicators.get("enough_history") else 0.50

    return {
        "signal_type": "pullback",
        "signal_grade": "B",
        "action": "BUY",
        "confidence": confidence,
        "reason": (
            f"回踩买入: 价{stock.get('price',0)}在MA20上方, "
            f"缩量{vol_ratio:.1f}, 回踩{ret}%"
        ),
    }


def detect_entry_sector_start(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    sector_now_breadth: float = 0,
    sector_prev_breadth: float = 0,
) -> dict[str, Any] | None:
    """
    C类: 板块启动买入

    条件: 板块刚晋级(昨日<6 今日≥6) + Breadth上升 + 个股是龙头
    """
    sector_score = sector_scored.get("score", 0)
    rank_in_sector = stock.get("rank_in_sector", 99)

    if sector_score < config.SIGNAL_SECTOR_UPGRADE_MIN:
        return None
    # 判断板块是否刚晋级
    if sector_prev_breadth >= config.BREADTH_MEDIUM:  # 不是新启动
        return None
    if sector_now_breadth <= sector_prev_breadth:  # Breadth未增强
        return None
    if rank_in_sector > 3:  # 只取龙头
        return None

    return {
        "signal_type": "sector_start",
        "signal_grade": "C",
        "action": "BUY",
        "confidence": 0.55,
        "reason": (
            f"板块启动: 板块{sector_scored.get('name','?')}刚晋级"
            f"({sector_score}分), Breadth{sector_prev_breadth:.0%}→{sector_now_breadth:.0%}"
        ),
    }


# ============================================================
# 卖出信号
# ============================================================

def detect_exit_trend_break(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    indicators: dict[str, Any],
) -> dict[str, Any] | None:
    """
    D类: 趋势破坏 (核心止损)

    条件: 价<MA20 + 放量下跌 + 板块<5
    """
    sector_score = sector_scored.get("score", 0)
    vol_ratio = stock.get("volume_ratio", 0)
    ret = stock.get("return", 0)

    if indicators.get("above_ma20", True):
        return None
    if sector_score >= config.SIGNAL_SECTOR_DANGER:
        return None  # 板块还安全
    if ret >= 0 and vol_ratio < 1.5:
        return None  # 没放量跌

    confidence = 0.90 if ret < -2 else 0.75

    return {
        "signal_type": "trend_break",
        "signal_grade": "D",
        "action": "SELL",
        "confidence": confidence,
        "reason": (
            f"趋势破坏: 价{stock.get('price',0)}<MA20{indicators.get('ma20',0):.2f}, "
            f"板块{sector_score}分, {'放量跌' if vol_ratio>1 else '缩量跌'}"
        ),
    }


def detect_exit_climax(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
    sector_prev_score: float = 0,
) -> dict[str, Any] | None:
    """
    E类: 高潮衰竭

    条件: 巨量(>3x) + 涨幅<3%(滞涨) + 板块score下降
    """
    vol_ratio = stock.get("volume_ratio", 0)
    ret = stock.get("return", 0)
    sector_score = sector_scored.get("score", 0)

    if vol_ratio < config.SIGNAL_EXIT_VOL_SPIKE:
        return None
    if ret > config.SIGNAL_EXIT_STAG_RETURN_MAX:  # 还在涨(不是滞涨)
        return None
    if sector_score >= sector_prev_score > 0:  # 板块没降
        return None

    return {
        "signal_type": "climax_exhaustion",
        "signal_grade": "E",
        "action": "SELL",
        "confidence": 0.70,
        "reason": (
            f"高潮衰竭: 巨量{vol_ratio:.1f}x+涨幅仅{ret}%, "
            f"板块{int(sector_prev_score)}→{int(sector_score)}降"
        ),
    }


def detect_exit_weaker(
    stock: dict[str, Any],
    sector_scored: dict[str, Any],
) -> dict[str, Any] | None:
    """
    F类: 弱于板块

    条件: 个股score<5 + 相对强度为负 + 板块仍强
    """
    stock_score = stock.get("score", 0)
    rs = stock.get("relative_strength", 0)
    sector_score = sector_scored.get("score", 0)

    if stock_score >= config.SIGNAL_EXIT_SCORE_WEAK:
        return None
    if rs >= 0:
        return None
    if sector_score < config.SECTOR_SCORE_QUALIFIED:  # 板块弱→归D类
        return None

    return {
        "signal_type": "weaker_than_sector",
        "signal_grade": "F",
        "action": "SELL",
        "confidence": 0.65,
        "reason": (
            f"弱于板块: 个股{stock_score}分, RS={rs}, "
            f"板块{sector_score}分(仍强), 建议淘汰"
        ),
    }
