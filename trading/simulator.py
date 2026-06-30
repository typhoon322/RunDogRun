"""
trading/simulator.py — v3.0 交易模拟器
=========================================
规则: score > threshold → 买入 → 持有 N 天 → 退出
输出: PnL curve, win_rate, sharpe, max_drawdown
"""
import json
import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_registry import DataRegistry

logger = logging.getLogger("v3.sim")


def simulate(
    df: pd.DataFrame,
    threshold: float = 60,
    hold_days: int = 5,
    horizon: int = 5,
) -> dict:
    """
    模拟交易: 每天取 score >= threshold 的股票, 持有 hold_days 天后退出。

    Args:
        df: signals_with_returns 数据
        threshold: 买入阈值
        hold_days: 持有天数
        horizon: 评估期限 (应与 ret_Nd 一致)

    Returns:
        {pnl_curve, metrics, signals_used}
    """
    col = f"ret_{horizon}d"
    if col not in df.columns:
        return {"error": f"无 ret_{horizon}d 列", "metrics": {}}

    trades = df[df["score"] >= threshold].dropna(subset=[col]).copy()
    if len(trades) < 2:
        return {"error": f"仅 {len(trades)} 条符合条件的信号", "metrics": {}}

    trades = trades.sort_values("signal_date")

    # 简单版本: 每信号独立, 资金等分
    returns = trades[col].tolist()
    n = len(returns)

    # PnL 曲线
    equity = 1.0
    curve = [1.0]
    for r in returns:
        equity *= (1 + r)
        curve.append(round(equity, 4))

    # 指标
    total_ret = round(equity - 1, 4)
    wr = round(sum(1 for r in returns if r > 0) / n, 3)
    avg_r = float(np.mean(returns))
    std_r = float(np.std(returns)) if n > 1 else 0
    sharpe = round(avg_r / std_r * (252 ** 0.5), 2) if std_r > 0 else 0

    peak = 1.0
    max_dd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)

    metrics = {
        "total_return": round(total_ret, 4),
        "win_rate": wr,
        "sharpe": sharpe,
        "max_drawdown": round(max_dd, 4),
        "n_trades": n,
    }

    result = {
        "pnl_curve": curve,
        "metrics": metrics,
        "threshold": threshold,
        "hold_days": hold_days,
        "dates": trades["signal_date"].tolist(),
    }

    # 保存
    os.makedirs("output", exist_ok=True)
    with open("output/sim_pnl.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def sim_report() -> dict:
    """模拟交易报告"""
    path = "data/signals/signals_with_returns.csv"
    if not os.path.exists(path):
        logger.warning("无信号数据")
        return {"error": "无信号数据"}

    df = pd.read_csv(path)
    sim = simulate(df, threshold=60)

    m = sim.get("metrics", {})
    print()
    print("─" * 40)
    print(f"  📉 模拟交易 (threshold=60)")
    print("─" * 40)
    print(f"  交易次数: {m.get('n_trades', 0)}")
    print(f"  总收益: {m.get('total_return', 0):+.2%}")
    print(f"  胜率: {m.get('win_rate', 0):.0%}")
    print(f"  夏普: {m.get('sharpe', 0)}")
    print(f"  最大回撤: {m.get('max_drawdown', 0):.2%}")
    print("─" * 40)

    return sim


if __name__ == "__main__":
    sim_report()
