"""
evaluator.py — v7 回测评估器 (真实PnL)
=========================================
从 backtest_engine 输出计算综合评分
"""
from typing import Any


def evaluate(backtest_result: dict[str, Any]) -> dict[str, Any]:
    """计算真实评估指标"""
    metrics = backtest_result.get("metrics", {})

    total_return = metrics.get("total_return_pct", 0)
    max_dd = metrics.get("max_drawdown_pct", 0)
    win_rate = metrics.get("win_rate", 0)
    profit_factor = metrics.get("profit_factor", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    trades = metrics.get("total_trades", 0)

    # 综合评分 (0-100)
    return_score = min(30, max(0, total_return / 3))
    risk_score = min(25, max(0, (15 + max_dd) / 15 * 25)) if max_dd > -15 else 25
    consistency = min(20, win_rate * 20)
    robustness = min(15, profit_factor * 5) if profit_factor < 3 else 15
    efficiency = min(10, max(0, sharpe * 5))

    score = round(return_score + risk_score + consistency + robustness + efficiency, 1)

    # 收益曲线分析
    equity_curve = backtest_result.get("equity_curve", [])
    peak_val = max(equity_curve) if equity_curve else 1.0
    final_val = equity_curve[-1] if equity_curve else 1.0

    return {
        "total_return_pct": round(total_return, 1),
        "max_drawdown_pct": round(max_dd, 1),
        "win_rate": round(win_rate, 2),
        "profit_factor": profit_factor,
        "sharpe_ratio": round(sharpe, 2),
        "total_trades": trades,
        "strategy_score": score,
        "final_equity": round(final_val, 4),
        "peak_equity": round(peak_val, 4),
        "rating": _rating(score),
    }


def _rating(score: float) -> str:
    if score >= 80:
        return "TRADE_READY"
    elif score >= 60:
        return "OPTIMIZABLE"
    elif score >= 40:
        return "STRUCTURAL_ISSUE"
    return "UNUSABLE"


def compute_sharpe(daily_returns: list[float]) -> float:
    """从日收益序列计算夏普比率"""
    if len(daily_returns) < 2:
        return 0.0
    avg = sum(daily_returns) / len(daily_returns)
    var = sum((r - avg) ** 2 for r in daily_returns) / len(daily_returns)
    if var <= 0:
        return 0.0
    return round((avg / (var ** 0.5)) * (252 ** 0.5), 2)


def compute_max_drawdown(equity_curve: list[float]) -> float:
    """计算最大回撤百分比"""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return round(max_dd * 100, 1)
