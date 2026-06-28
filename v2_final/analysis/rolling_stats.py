"""
v2_final/analysis/rolling_stats.py — v2.5 连续绩效追踪
===========================================================
滑动窗口统计: win_rate / volatility / sharpe (20日滚动)
"""
from collections import deque
from typing import Any


class RollingStats:
    """20日滑动窗口统计"""

    def __init__(self, window: int = 20):
        self.window = window
        self.returns = deque(maxlen=window)
        self.values = deque(maxlen=window)

    def update(self, equity_curve: list[float]) -> dict[str, Any] | None:
        """喂入最新净值曲线, 提取增量统计"""
        if len(equity_curve) < 2:
            return None

        r = (equity_curve[-1] - equity_curve[-2]) / equity_curve[-2] if equity_curve[-2] > 0 else 0
        self.returns.append(r)
        self.values.append(equity_curve[-1])

        return self.stats()

    def stats(self) -> dict[str, Any]:
        if not self.returns:
            return {"win_rate": 0, "volatility": 0, "sharpe": 0, "n": 0}

        n = len(self.returns)
        wins = sum(1 for r in self.returns if r > 0)
        win_rate = round(wins / n, 3)

        avg = sum(self.returns) / n
        var = sum((r - avg) ** 2 for r in self.returns) / n
        volatility = round(var ** 0.5, 4)

        # 滚动夏普
        risk_free_daily = 0.02 / 252
        excess = avg - risk_free_daily
        sharpe = round(excess / (volatility + 1e-9) * (252 ** 0.5), 2)

        return {
            "win_rate": win_rate,
            "volatility": volatility,
            "sharpe": sharpe,
            "avg_return": round(avg, 4),
            "n": n,
        }
