"""
reward.py — v11 奖励函数
==========================
Reward = PnL × 1.0 - Drawdown × 1.5 - Risk × 0.8 - Turnover × 0.2

驱动因子: 收益 > 回撤控制 > 风险控制 > 交易频率
"""
import logging
from typing import Any

logger = logging.getLogger("quant.v11.reward")


def compute_reward(
    trade: dict[str, Any],
    portfolio: dict[str, Any],
) -> float:
    """
    计算单笔交易奖励。

    Args:
        trade: {action, entry_price, exit_price, pnl_pct, hold_days}
        portfolio: {drawdown_pct, total_exposure, daily_trades}

    Returns:
        reward 值 (-3.0 ~ 3.0)
    """
    # 1. PnL 收益 (0~2)
    pnl = trade.get("pnl_pct", 0)
    pnl_reward = min(2.0, max(-2.0, pnl / 5))

    # 2. 回撤惩罚 (0~-1.5)
    drawdown = abs(portfolio.get("drawdown_pct", 0))
    dd_penalty = min(1.5, drawdown / 100 * 1.5)

    # 3. 风险惩罚 (仓位过高)
    exposure = portfolio.get("total_exposure", 0)
    risk_penalty = max(0.0, (exposure - 0.5) * 0.8) if exposure > 0.5 else 0

    # 4. 过度交易惩罚
    daily_trades = portfolio.get("daily_trades", 0)
    turnover_penalty = max(0.0, (daily_trades - 10) * 0.02)

    # 5. 持仓天数奖励 (中线: 持有越久越好, 上限5天)
    hold_days = trade.get("hold_days", 1)
    hold_bonus = min(0.3, hold_days * 0.1) if pnl > 0 else 0

    reward = pnl_reward - dd_penalty - risk_penalty - turnover_penalty + hold_bonus
    return round(reward, 3)


def compute_trade_pnl(
    entry_price: float,
    exit_price: float,
    side: str = "BUY",
    size: float = 1.0,
) -> float:
    """计算单笔交易盈亏百分比"""
    if entry_price <= 0:
        return 0
    if side in ("BUY", "ENTRY"):
        return round((exit_price - entry_price) / entry_price * 100, 2)
    else:  # SELL
        return round((entry_price - exit_price) / entry_price * 100, 2)
