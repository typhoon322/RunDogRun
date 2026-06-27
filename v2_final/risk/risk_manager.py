"""
v2_final/risk/risk_manager.py — 极简风控
===========================================
核心: 仓位上限 + 置信度过滤 + 单票上限 + 止损
"""
from typing import Any


def risk_check(signal: dict, portfolio: dict) -> tuple[bool, str]:
    """预交易风控检查"""
    action = signal.get("action", "HOLD")
    if action != "BUY":
        return True, "HOLD"

    # 1. 仓位上限
    exposure = portfolio.get("exposure", 0)
    if exposure >= 0.60:
        return False, f"仓位超限: {exposure:.0%} >= 60%"

    # 2. 置信度过滤
    confidence = signal.get("confidence", 0)
    if confidence < 0.60:
        return False, f"置信度不足: {confidence:.0%}"

    # 3. 最大持仓数
    positions = portfolio.get("positions", 0)
    if positions >= 5:
        return False, f"持仓数已满: {positions}/5"

    # 4. 单票上限
    if portfolio.get("single_exposure", 0) >= 0.30:
        return False, "单票超30%"

    return True, "ok"


def calc_position_size(confidence: float, exposure: float) -> float:
    """仓位计算: 置信度 × 可用空间"""
    available = max(0, 0.60 - exposure)
    size = min(0.20, available * confidence / 0.75)
    return round(size, 2)


def stop_loss_check(entry_price: float, current_price: float) -> tuple[bool, float]:
    """止损检查"""
    if entry_price <= 0:
        return False, 0
    pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
    return pnl_pct <= -8, pnl_pct  # -8% 止损
