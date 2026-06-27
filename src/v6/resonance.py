"""
resonance.py — v6 多周期共振引擎 (真实信号版)
================================================
公式:
  Final Resonance = 0.5*Multi-Timeframe + 0.3*Sector + 0.2*Volatility

三周期:
  日线: EMA(5) > EMA(20)
  周线: close_week > EMA_10_week
  月线: close_month > EMA_6_month
"""
import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v6.resonance")


def compute_resonance_real(
    stock: dict[str, Any],
    sector: dict[str, Any],
    price_history: list[dict[str, Any]],
    market_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    真实多周期共振计算 (基于历史价格数据)

    Returns:
        {multi_timeframe, sector_alignment, volatility, resonance_score, state}
    """
    code = stock.get("code", "")

    # 1. 多周期趋势
    mtf = _compute_multi_timeframe(code, price_history, stock)

    # 2. 板块共振
    sector_align = _compute_sector_alignment(sector, stock, price_history)

    # 3. 波动率
    volatility = _compute_volatility(code, price_history)

    # 4. 最终共振分
    final_score = round(
        0.5 * mtf["score"] +
        0.3 * sector_align +
        0.2 * (1 - volatility),  # 低波动 = 高分
        3
    )

    # 状态
    if final_score > 0.7:
        state = "strong_alignment"
    elif final_score > 0.5:
        state = "moderate"
    elif final_score > 0.3:
        state = "weak"
    else:
        state = "conflict"

    return {
        "code": code,
        "name": stock.get("name", ""),
        "multi_timeframe": mtf,
        "sector_alignment": round(sector_align, 3),
        "volatility": round(volatility, 3),
        "resonance_score": final_score,
        "state": state,
    }


def _compute_multi_timeframe(code: str, history: list[dict], stock: dict) -> dict[str, Any]:
    """
    三周期趋势计算:
      daily:  EMA(5) > EMA(20)
      weekly: 5日均 > 10日均 (周代理)
      monthly: 20日均 > 40日均 (月代理)

    Returns:
        {daily, weekly, monthly, score}
    """
    prices = _collect_prices(code, history, stock)
    if len(prices) < 5:
        return {"daily": False, "weekly": False, "monthly": False, "score": 0.0}

    n = len(prices)

    # 日线: EMA5 > EMA20
    ema5 = _ema(prices, 5)[-1] if n >= 5 else prices[-1]
    ema20 = _ema(prices, 20)[-1] if n >= 20 else _sma(prices, min(n, 5))
    daily = ema5 > ema20

    # 周线: 用5日均价 > 10日均价作为代理
    sma5 = _sma(prices, min(5, n))
    sma10 = _sma(prices, min(10, n))
    weekly = sma5 > sma10 if n >= 5 else daily

    # 月线: 20日 > 40日
    sma20 = _sma(prices, min(20, n))
    sma40 = _sma(prices, min(40, n)) if n >= 40 else sma20
    monthly = sma20 > sma40 if n >= 20 else daily

    # 加权分: 日0.4 + 周0.35 + 月0.25
    score = (0.4 if daily else 0) + (0.35 if weekly else 0) + (0.25 if monthly else 0)

    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "score": round(score, 2),
    }


def _compute_sector_alignment(sector: dict, stock: dict, history: list[dict]) -> float:
    """
    板块共振 = 0.35*rising_ratio + 0.35*leader_pct + 0.3*volume_expansion
    """
    # 上涨家数占比
    total = sector.get("total_stocks", 1)
    up = sector.get("up_count", 0)
    rising_ratio = up / total if total > 0 else 0

    # 龙头强度 (领涨股涨幅 / 板块涨幅)
    leader_pct = sector.get("leader_change_pct", 0)
    sector_pct = sector.get("change_pct", 0.01)
    if abs(sector_pct) < 0.01:
        leader_strength = 0.5
    else:
        leader_strength = min(1.0, max(0.0, (leader_pct / sector_pct) * 0.5)) if sector_pct > 0 else 0.3

    # 成交量扩张 (当前量比 vs 历史)
    vol = stock.get("volume_ratio", 1.0)
    vol_expansion = min(1.0, (vol - 0.8) / 0.7) if vol > 0.8 else 0.0

    return round(0.35 * rising_ratio + 0.35 * leader_strength + 0.3 * vol_expansion, 3)


def _compute_volatility(code: str, history: list[dict]) -> float:
    """计算波动率 (0-1, 越低越好)"""
    returns = _collect_returns(code, history)
    if len(returns) < 3:
        return 0.5

    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / len(returns)
    sigma = var ** 0.5

    # 归一化: sigma在 0-5% 之间映射到 0-1
    return round(min(1.0, sigma / 5), 3)


# ── 辅助函数 ──

def _collect_prices(code: str, history: list[dict], stock: dict) -> list[float]:
    prices = []
    for h in history:
        for s in h.get("stocks", []):
            if s.get("code") == code:
                p = s.get("price", 0)
                if p > 0:
                    prices.append(p)
                break
    cur = stock.get("price", 0)
    if cur > 0:
        prices.append(cur)
    return prices


def _collect_returns(code: str, history: list[dict]) -> list[float]:
    returns = []
    for h in history:
        for s in h.get("stocks", []):
            if s.get("code") == code:
                returns.append(s.get("return", 0))
                break
    return returns


def _sma(prices: list[float], period: int) -> float:
    if not prices:
        return 0
    window = prices[-period:]
    return sum(window) / len(window)


def _ema(prices: list[float], period: int) -> list[float]:
    if not prices or len(prices) < 2:
        return prices
    k = 2 / (period + 1)
    result = [prices[0]]
    for p in prices[1:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def compute_overall_resonance(
    sector_resonances: list[dict[str, Any]],
    stocks_resonances: list[dict[str, Any]],
) -> dict[str, Any]:
    """汇总整体共振状态"""
    if not sector_resonances and not stocks_resonances:
        return {"score": 0.0, "label": "conflict"}

    scores = [r.get("resonance_score", 0) for r in stocks_resonances]
    avg = sum(scores) / len(scores) if scores else 0

    strong = sum(1 for r in stocks_resonances if r.get("state") == "strong_alignment")
    moderate = sum(1 for r in stocks_resonances if r.get("state") == "moderate")

    if avg > 0.7:
        label = "strong_alignment"
    elif avg > 0.5:
        label = "moderate"
    elif avg > 0.3:
        label = "weak"
    else:
        label = "conflict"

    return {
        "score": round(avg, 3),
        "label": label,
        "strong_count": strong,
        "moderate_count": moderate,
        "total": len(scores),
    }


# ── 向后兼容 ──

def compute_resonance(multi_cycle_data: dict, sectors: list, stocks: list) -> dict[str, Any]:
    """兼容旧接口: 从 multi_cycle 数据计算整体共振"""
    resonances = []
    for stk in stocks[:20]:
        sec = next((s for s in sectors if s.get("name") == stk.get("sector", "")), {})
        code = stk.get("code", "")
        r = compute_resonance_real(stk, sec, [])
        resonances.append(r)

    overall = compute_overall_resonance([], resonances)
    sectors_map = {}
    for r in resonances:
        if r.get("code"):
            sectors_map[r["code"]] = {"score": r["resonance_score"],
                                       "label": r["state"]}
    return {"overall": overall, "sectors": sectors_map}
