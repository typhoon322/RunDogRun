"""
v2_final/backtest/backtester.py — 历史回测引擎
==================================================
基于 AKShare 日线数据 + v2.2 信号策略, 模拟完整交易
"""
import logging
from typing import Any, Callable

logger = logging.getLogger("v2.backtest")


def backtest(
    df,
    signal_func: Callable,
    initial_cash: float = 1.0,
    position_size: float = 0.30,
    start_idx: int = 20,
) -> dict[str, Any]:
    """
    完整历史回测。

    Args:
        df: pandas DataFrame (需含 close/volume/pct 列)
        signal_func: 信号生成函数, 接收 sub_df → {action, confidence}
        initial_cash: 初始资金
        position_size: 每次仓位比例
        start_idx: 开始回测的索引 (留足够数据计算均线)

    Returns:
        {equity_curve, trades, metrics}
    """
    cash = initial_cash
    position = 0.0   # 持仓市值
    equity_curve = [initial_cash]
    trades: list[dict] = []
    entry_price = 0.0

    for i in range(start_idx, len(df)):
        sub_df = df.iloc[:i]
        price = float(df.iloc[i]["close"])
        signal = signal_func(sub_df)

        action = signal.get("action", "HOLD")

        if action == "BUY" and position == 0:
            # 开仓
            pos_value = cash * position_size
            position = pos_value
            cash -= pos_value
            entry_price = price
            trades.append({
                "idx": i, "action": "BUY", "price": round(price, 2),
                "size": round(position_size, 2),
            })

        elif action == "SELL" and position > 0:
            # 平仓
            cash += position * (price / entry_price) if entry_price > 0 else position
            pnl = round((price / entry_price - 1) * 100, 2) if entry_price > 0 else 0
            trades.append({
                "idx": i, "action": "SELL", "price": round(price, 2),
                "entry_price": round(entry_price, 2), "pnl_pct": pnl,
            })
            position = 0
            entry_price = 0

        # 标记到市场
        equity = cash + (position * (price / entry_price) if entry_price > 0 else position)
        equity_curve.append(round(equity, 4))

    # 未平仓结算
    if position > 0 and len(df) > 0:
        final_price = float(df.iloc[-1]["close"])
        equity = cash + (position * (final_price / entry_price) if entry_price > 0 else position)
        equity_curve[-1] = round(equity, 4)

    # 绩效指标
    metrics = _compute_metrics(equity_curve, trades)

    return {
        "equity_curve": equity_curve,
        "trades": trades,
        "metrics": metrics,
        "total_trades": len([t for t in trades if t["action"] == "SELL"]),
    }


def _compute_metrics(equity: list[float], trades: list[dict]) -> dict[str, Any]:
    n = len(equity)
    if n < 2:
        return {"win_rate": 0, "max_drawdown": 0, "total_return": 0}

    # 总收益
    total_return = round((equity[-1] / equity[0] - 1) * 100, 2)

    # 最大回撤
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    max_dd_pct = round(max_dd * 100, 2)

    # 胜率
    closed = [t for t in trades if t.get("pnl_pct") is not None]
    wins = sum(1 for t in closed if t.get("pnl_pct", 0) > 0)
    win_rate = round(wins / len(closed), 2) if closed else 0.0

    # 平均盈亏
    avg_win = sum(t["pnl_pct"] for t in closed if t.get("pnl_pct", 0) > 0) / max(1, wins)
    losses = [t["pnl_pct"] for t in closed if t.get("pnl_pct", 0) <= 0]
    avg_loss = sum(losses) / len(losses) if losses else 0

    # 年化 (假设250交易日)
    days = len(equity) - 1
    annual = round(((equity[-1] / equity[0]) ** (250 / days) - 1) * 100, 2) if days > 0 else 0

    return {
        "total_return_pct": total_return,
        "annual_return_pct": annual,
        "max_drawdown_pct": max_dd_pct,
        "win_rate": win_rate,
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "total_closed_trades": len(closed),
    }
