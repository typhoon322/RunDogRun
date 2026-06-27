"""
v2_final/risk/risk_manager.py — v2.2 动态风控
=================================================
仓位计算 + 回撤控制 + 自适应胜率 + 熔断
"""
from typing import Any


def risk_check(signal: dict, portfolio: dict) -> tuple[bool, str]:
    """v2.1 预交易风控检查"""
    action = signal.get("action", "HOLD")
    if action != "BUY":
        return True, "HOLD"

    exposure = portfolio.get("exposure", 0)
    if exposure >= 0.60:
        return False, f"仓位超限: {exposure:.0%}"

    confidence = signal.get("confidence", 0)
    if confidence < 0.55:
        return False, f"置信度不足: {confidence:.0%}"

    positions = portfolio.get("positions", 0)
    if positions >= 5:
        return False, "持仓已满"

    return True, "ok"


def calc_position_size(confidence: float, exposure: float,
                        volatility: float = 0.4) -> float:
    """v2.1 动态仓位: 置信度 × 波动率折扣 × 可用空间"""
    base = 0.20
    vol_discount = max(0.3, 1 - volatility)
    size = base * confidence * vol_discount
    available = max(0, 0.60 - exposure)
    return round(min(size, available, 0.35), 2)


def check_drawdown(equity_curve: list[float]) -> str:
    """v2.2 回撤控制"""
    if not equity_curve or len(equity_curve) < 2:
        return "OK"

    peak = max(equity_curve)
    current = equity_curve[-1]
    if peak <= 0:
        return "OK"

    dd = (peak - current) / peak

    if dd > 0.12:
        return "STOP_TRADING"
    if dd > 0.08:
        return "REDUCE_RISK"
    return "OK"


def stop_loss_check(entry_price: float, current_price: float) -> tuple[bool, float]:
    """v2.1 止损 -8%"""
    if entry_price <= 0:
        return False, 0
    pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
    return pnl_pct <= -8, pnl_pct
