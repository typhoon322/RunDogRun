"""
v2_final/analysis/performance.py — 回测绩效分析
===================================================
win_rate / max_drawdown / total_return / sharpe
"""
import math
from typing import Any


def analyze_equity(equity_curve: list[float]) -> dict[str, Any]:
    """从净值曲线计算完整指标"""
    n = len(equity_curve)
    if n < 2:
        return {"total_return": 0, "win_rate": 0, "max_drawdown": 0, "score": 0}

    # 收益率序列
    returns = [(equity_curve[i] / equity_curve[i - 1] - 1)
               for i in range(1, n)]

    win_rate = round(sum(1 for r in returns if r > 0) / len(returns), 2)

    max_dd = _max_drawdown(equity_curve)
    total_return = round(equity_curve[-1] / equity_curve[0] - 1, 4)

    # 夏普
    avg_r = sum(returns) / len(returns)
    var = sum((r - avg_r) ** 2 for r in returns) / len(returns)
    sharpe = round((avg_r / math.sqrt(var)) * math.sqrt(252), 2) if var > 0 else 0

    # 策略评分
    score = round(
        total_return * 100 * 0.4 +
        (1 - max_dd) * 30 +
        win_rate * 20 +
        max(0, sharpe) * 10,
        1
    )

    return {
        "total_return": round(total_return * 100, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": win_rate,
        "sharpe": sharpe,
        "score": score,
        "rating": _rating(score),
    }


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def _rating(score: float) -> str:
    if score >= 50:
        return "GOOD"
    elif score >= 30:
        return "OK"
    elif score >= 10:
        return "WEAK"
    return "POOR"
