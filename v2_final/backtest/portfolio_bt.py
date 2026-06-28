"""
v2_final/backtest/portfolio_bt.py — v2.3 组合回测
=====================================================
多股票加权净值曲线 + 再平衡
"""
import logging
from typing import Any

logger = logging.getLogger("v2.portfolio_bt")


def backtest_portfolio(
    portfolio: list[dict],
    price_data: dict[str, list[float]],
    initial_cash: float = 1.0,
    rebalance_freq: int = 20,
) -> dict[str, Any]:
    """
    组合回测 — 加权日收益。

    Args:
        portfolio: [{code, weight}, ...]
        price_data: {code: [price_0, price_1, ...]}
        initial_cash: 初始资金
        rebalance_freq: 再平衡频率 (交易日)

    Returns:
        {equity_curve, metrics}
    """
    # 对齐长度
    lengths = [len(v) for v in price_data.values()]
    if not lengths:
        return {"equity_curve": [initial_cash], "metrics": {"error": "no data"}}

    n_days = min(lengths)
    if n_days < 5:
        return {"equity_curve": [initial_cash], "metrics": {"error": "insufficient data"}}

    weights = {p["code"]: p["weight"] for p in portfolio}
    equity = initial_cash
    equity_curve = [initial_cash]
    daily_returns = []

    # 初始持仓分配
    holdings = {}
    for code, w in weights.items():
        holdings[code] = (equity * w) / price_data[code][0] if price_data[code][0] > 0 else 0

    for day in range(1, n_days):
        # 计算当日市值
        day_value = 0.0
        for code, shares in holdings.items():
            prices = price_data.get(code, [])
            if day < len(prices):
                day_value += shares * prices[day]

        if day_value <= 0:
            day_value = equity

        daily_ret = (day_value / equity - 1) if equity > 0 else 0
        daily_returns.append(daily_ret)
        equity = day_value
        equity_curve.append(round(equity, 4))

        # 再平衡
        if day % rebalance_freq == 0:
            for code, w in weights.items():
                prices = price_data.get(code, [])
                if day < len(prices) and prices[day] > 0:
                    holdings[code] = (equity * w) / prices[day]

    metrics = _compute_metrics(equity_curve, daily_returns)

    logger.info(f"组合回测: {n_days}天 收益{metrics['total_return']:.1f}% "
                f"回撤{metrics['max_drawdown']:.1f}% sharpe={metrics['sharpe']}")

    return {"equity_curve": equity_curve, "metrics": metrics}


def _compute_metrics(equity: list[float], daily_returns: list[float]) -> dict[str, Any]:
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

    wr = round(sum(1 for r in daily_returns if r > 0) / len(daily_returns), 2)

    avg_r = sum(daily_returns) / len(daily_returns)
    var = sum((r - avg_r) ** 2 for r in daily_returns) / len(daily_returns)
    sharpe = round(avg_r / (var ** 0.5) * (252 ** 0.5), 2) if var > 0 else 0

    return {
        "total_return": total_return,
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe": sharpe,
        "win_rate": wr,
        "volatility": round((var ** 0.5) * 100, 2) if var > 0 else 0,
    }


def fetch_prices_for_portfolio(portfolio: list[dict], start_date: str = "20240101") -> dict[str, list[float]]:
    """
    批量拉取组合中所有股票的历史价格。

    Returns:
        {code: [price_0, price_1, ...]}
    """
    import akshare as ak
    price_data = {}

    for p in portfolio:
        code = p["code"]
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                     start_date=start_date, adjust="qfq")
            if df.empty:
                logger.warning(f"  {code} 无数据")
                continue
            prices = [float(v) for v in df["收盘"].values]
            price_data[code] = prices
            logger.debug(f"  {code} {p['name']}: {len(prices)} 条")
        except Exception as e:
            logger.warning(f"  {code} 获取失败: {e}")

    return price_data
