"""
leader_engine.py — v3 龙头识别引擎 (真实信号版)
===================================================
5维真实评分: RS / Momentum / Volume Persistence / Breakout / Market Sync

公式:
  Leader Score = 0.35*RS + 0.20*Momentum + 0.15*VP + 0.15*BS + 0.15*MS
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v3.leader")


def compute_leader_score(
    stock: dict[str, Any],
    sector: dict[str, Any],
    price_history: list[dict[str, Any]],
    stock_scores: dict[str, Any] | None = None,
    hot_codes: set[str] | None = None,
) -> dict[str, Any]:
    """计算5维龙头评分"""

    # 1. 相对强度 RS (0-1)
    rs = _compute_rs(stock, sector, price_history)

    # 2. 动量加速度 (0-1)
    momentum = _compute_momentum(stock, price_history)

    # 3. 成交量持续性 (0-1)
    vol_persistence = _compute_volume_persistence(stock, price_history)

    # 4. 突破强度 (0-1)
    breakout = _compute_breakout_strength(stock, price_history)

    # 5. 市场同步度 (0-1)
    market_sync = _compute_market_sync(stock, sector, price_history, hot_codes)

    # 加权总分
    score = (
        0.35 * rs +
        0.20 * momentum +
        0.15 * vol_persistence +
        0.15 * breakout +
        0.15 * market_sync
    )

    # 阶段判定
    if score > 0.7:
        stage = "main_trend"
    elif score > 0.5:
        stage = "test"
    elif score > 0.3:
        stage = "accumulation"
    else:
        stage = "weak"

    return {
        "code": stock.get("code", ""),
        "name": stock.get("name", ""),
        "sector": stock.get("sector", ""),
        "leader_score": round(score, 3),
        "rs": round(rs, 3),
        "momentum": round(momentum, 3),
        "volume_persistence": round(vol_persistence, 3),
        "breakout_strength": round(breakout, 3),
        "market_sync": round(market_sync, 3),
        "stage": stage,
        "stage_label": {"main_trend": "主升期", "test": "试盘期", "accumulation": "启动期", "weak": "弱势"}[stage],
    }


def _compute_rs(stock: dict, sector: dict, history: list[dict]) -> float:
    """
    RS = stock_return_5d / max(sector_return_5d, 0.01)
    归一化到 0-1: tanh(RS * 3)
    """
    stock_ret = _n_day_return(history, 5, stock.get("code", ""))
    sector_ret = sector.get("change_pct", 0.01)

    if abs(sector_ret) < 0.01:
        sector_ret = 0.01

    rs_raw = stock_ret / sector_ret if sector_ret > 0 else (stock_ret / abs(sector_ret) * -1)
    # tanh 归一化
    import math
    return round((math.tanh(rs_raw * 3) + 1) / 2, 3)


def _compute_momentum(stock: dict, history: list[dict]) -> float:
    """
    MA = (close_today - close_5d_ago) / close_5d_ago
    归一化: sigmoid(MA * 10)
    """
    price = stock.get("price", 0)
    prev = _n_day_price(history, 5, stock.get("code", ""))
    if prev <= 0:
        return 0.5

    raw = (price - prev) / prev
    import math
    return round(1 / (1 + math.exp(-raw * 10)), 3)


def _compute_volume_persistence(stock: dict, history: list[dict]) -> float:
    """
    VP = avg_volume_ratio_5d / avg_volume_ratio_20d
    归一化: min(VP / 2, 1.0)
    """
    code = stock.get("code", "")
    vols_5 = _n_day_volumes(history, 5, code)
    vols_20 = _n_day_volumes(history, 20, code)

    avg5 = sum(vols_5) / len(vols_5) if vols_5 else 1.0
    avg20 = sum(vols_20) / len(vols_20) if vols_20 else 1.0

    if avg20 <= 0:
        return 0.5

    vp = avg5 / avg20
    return round(min(vp / 2, 1.0), 3)


def _compute_breakout_strength(stock: dict, history: list[dict]) -> float:
    """
    BS = (close - 20_day_high) / 20_day_high
    归一化: sigmoid(BS * 20)
    """
    price = stock.get("price", 0)
    code = stock.get("code", "")
    highs = _n_day_highs(history, 20, code)

    if not highs or max(highs) <= 0:
        return 0.5

    peak = max(highs)
    bs = (price - peak) / peak
    import math
    return round(1 / (1 + math.exp(-bs * 20)), 3)


def _compute_market_sync(stock: dict, sector: dict, history: list[dict],
                          hot_codes: set | None = None) -> float:
    """
    MS = 0.5 * stock_sector_corr + 0.3 * hot_attention + 0.2 * breadth
    """
    code = stock.get("code", "")
    # 1. 个股与板块涨跌相关性 (简化: 用最近5天同向天数)
    same_direction = 0
    sector_hist = [sector.get("change_pct", 0)] * 5  # 简化: 当日板块数据
    stock_returns = _n_day_returns(history, 5, code)
    for i, sr in enumerate(stock_returns):
        sh = sector_hist[min(i, len(sector_hist) - 1)]
        if (sr > 0 and sh > 0) or (sr < 0 and sh < 0):
            same_direction += 1
    corr = same_direction / max(1, len(stock_returns))

    # 2. 热点关注 (是否在同花顺热点中)
    hot_bonus = 1.0 if hot_codes and code in hot_codes else 0.3

    # 3. 板块宽度
    total = sector.get("total_stocks", 1)
    up = sector.get("up_count", 0)
    breadth = up / total if total > 0 else 0

    return round(0.5 * corr + 0.3 * hot_bonus + 0.2 * breadth, 3)


# ── 历史数据辅助函数 ──

def _n_day_return(history: list[dict], n: int, code: str) -> float:
    """最近N天累计收益"""
    returns = _n_day_returns(history, n, code)
    return sum(returns) if returns else 0


def _n_day_returns(history: list[dict], n: int, code: str) -> list[float]:
    """最近N天收益序列"""
    result = []
    for h in history[-n:]:
        for s in h.get("stocks", []):
            if s.get("code") == code:
                result.append(s.get("return", 0))
                break
    return result


def _n_day_price(history: list[dict], n: int, code: str) -> float:
    """N天前价格"""
    if len(history) < n:
        return 0
    for s in history[-n].get("stocks", []):
        if s.get("code") == code:
            return s.get("price", 0)
    return 0


def _n_day_volumes(history: list[dict], n: int, code: str) -> list[float]:
    """最近N天量比"""
    vols = []
    for h in history[-n:]:
        for s in h.get("stocks", []):
            if s.get("code") == code:
                vols.append(s.get("volume_ratio", 1.0))
                break
    return vols


def _n_day_highs(history: list[dict], n: int, code: str) -> list[float]:
    """最近N天最高价"""
    highs = []
    for h in history[-n:]:
        for s in h.get("stocks", []):
            if s.get("code") == code:
                highs.append(s.get("high", s.get("price", 0)))
                break
    return highs
