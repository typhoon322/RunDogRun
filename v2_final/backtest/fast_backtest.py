"""
v2_final/backtest/fast_backtest.py — 统一数据入口快速回测
=============================================================
所有回测强制通过 DataRegistry → 不再直接读文件
"""
import logging
from typing import Any

from core.data_registry import DataRegistry

logger = logging.getLogger("v2.fast_bt")


def backtest_from_cache(
    portfolio: list[dict],
    start_date: str = "20230101",
) -> dict[str, Any]:
    """通过 DataRegistry 统一入口执行组合回测"""
    registry = DataRegistry()
    codes = [p["code"] for p in portfolio]

    price_data = registry.get_prices(codes)
    registry.print_manifest()

    if len(price_data) < 2:
        return {"equity_curve": [1.0], "metrics": {"error": "insufficient data"}}

    # 对齐长度
    n_days = min(len(v) for v in price_data.values())
    weights = {p["code"]: p["weight"] for p in portfolio}

    equity = 1.0
    equity_curve = [1.0]

    for day in range(1, n_days):
        daily_return = 0.0
        for code, w in weights.items():
            prices = price_data.get(code, [])
            if day < len(prices) and prices[day - 1] > 0:
                r = (prices[day] - prices[day - 1]) / prices[day - 1]
                daily_return += w * r
        equity *= (1 + daily_return)
        equity_curve.append(round(equity, 4))

    return {"equity_curve": equity_curve, "metrics": _metrics(equity_curve)}


def _metrics(equity: list[float]) -> dict[str, Any]:
    n = len(equity)
    if n < 2:
        return {"total_return": 0, "max_drawdown": 0, "sharpe": 0, "win_rate": 0}
    total_return = round((equity[-1] / equity[0] - 1) * 100, 2)
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak: peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    returns = [(equity[i] - equity[i - 1]) / equity[i - 1] if equity[i - 1] != 0 else 0
               for i in range(1, n)]
    returns = [r for r in returns if not (isinstance(r, float) and (r != r))]  # 去 NaN
    if not returns:
        return {"total_return": 0, "max_drawdown": 0, "sharpe": 0, "win_rate": 0}
    wr = round(sum(1 for r in returns if r > 0) / len(returns), 2)
    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / len(returns)
    vol = (var ** 0.5) * 100 if var > 0 else 0
    sharpe = round(avg / (var ** 0.5) * (252 ** 0.5), 2) if var > 0 else 0
    return {
        "total_return": total_return,
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe": sharpe, "win_rate": wr,
        "volatility": round(vol, 2),
    }
