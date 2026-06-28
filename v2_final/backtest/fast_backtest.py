"""
v2_final/backtest/fast_backtest.py — 本地缓存快速回测
=========================================================
read data/raw/daily/*.csv → weighted portfolio backtest
比 AKShare 实时请求快 10-50x
"""
import logging
from typing import Any

from v2_final.data.collector import load_local_data, batch_collect

logger = logging.getLogger("v2.fast_bt")


def backtest_from_cache(
    portfolio: list[dict],
    start_date: str = "20230101",
) -> dict[str, Any]:
    """
    从本地 data/raw/daily/ CSV 读取历史, 执行组合回测。

    Returns:
        {equity_curve, metrics}
    """
    # 确保所有股票已缓存
    codes = [p["code"] for p in portfolio]
    batch_collect(codes)

    # 加载数据
    price_data = {}
    for p in portfolio:
        code = p["code"]
        df = load_local_data(code)
        if df is None or df.empty:
            logger.warning(f"  {code} 无本地数据")
            continue

        # 过滤起始日期
        df = df[df["date"] >= start_date]
        prices = [float(v) for v in df["close"].values]
        if prices:
            price_data[code] = prices
            logger.debug(f"  {code}: {len(prices)} 条 (from cache)")

    if len(price_data) < 2:
        return {"equity_curve": [1.0], "metrics": {"error": "insufficient cached data"}}

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

    metrics = _metrics(equity_curve)
    logger.info(f"快速回测(fs): {n_days}天 收益{metrics['total_return']:.1f}% "
                f"dd={metrics['max_drawdown']:.1f}%")

    return {"equity_curve": equity_curve, "metrics": metrics}


def _metrics(equity: list[float]) -> dict[str, Any]:
    n = len(equity)
    if n < 2:
        return {"total_return": 0, "max_drawdown": 0, "sharpe": 0, "win_rate": 0}

    total_return = round((equity[-1] / equity[0] - 1) * 100, 2)

    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)

    returns = [(equity[i] - equity[i - 1]) / equity[i - 1] for i in range(1, n)]
    wr = round(sum(1 for r in returns if r > 0) / len(returns), 2)
    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / len(returns)
    vol = (var ** 0.5) * 100 if var > 0 else 0
    sharpe = round(avg / (var ** 0.5) * (252 ** 0.5), 2) if var > 0 else 0

    return {
        "total_return": total_return,
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe": sharpe,
        "win_rate": wr,
        "volatility": round(vol, 2),
    }
