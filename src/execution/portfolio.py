"""
portfolio.py — 组合追踪器
===========================
跟踪模拟/实盘组合状态: 现金/持仓/净值/回撤
"""
import logging
from typing import Any

logger = logging.getLogger("quant.execution.portfolio")


class PortfolioTracker:
    """组合追踪器"""

    def __init__(self, initial_cash: float = 1.0):
        self.cash = initial_cash
        self.holdings: dict[str, dict] = {}  # {code: {shares, avg_price}}
        self.equity_curve: list[float] = [initial_cash]
        self.peak_value = initial_cash

    def apply_execution(self, result: dict, signal: dict) -> None:
        """根据执行结果更新持仓"""
        if not result.get("filled"):
            return

        code = signal.get("code", "")
        price = result.get("fill_price", signal.get("price", 0))
        if price <= 0:
            return

        action = signal.get("action", "")
        size = signal.get("position_size", 0)

        if action in ("BUY", "BUY_TRIAL", "ADD", "ENTRY"):
            # 买入: 仓位比例 → 股票数量
            cost = self.cash * size
            shares = cost / price
            self.cash -= cost
            if code in self.holdings:
                old = self.holdings[code]
                total_shares = old["shares"] + shares
                old["avg_price"] = (old["avg_price"] * old["shares"] + price * shares) / total_shares
                old["shares"] = total_shares
            else:
                self.holdings[code] = {"shares": shares, "avg_price": price}

        elif action in ("SELL", "REDUCE", "EMPTY"):
            if code in self.holdings:
                h = self.holdings[code]
                sell_shares = h["shares"] * abs(size) if size < 0 else h["shares"]
                self.cash += sell_shares * price
                del self.holdings[code]

        # 更新净值
        total = self.cash + self._holdings_value({signal.get("code", ""): price})
        self.equity_curve.append(total)
        if total > self.peak_value:
            self.peak_value = total

    def _holdings_value(self, prices: dict[str, float]) -> float:
        return sum(h["shares"] * prices.get(code, h["avg_price"])
                   for code, h in self.holdings.items())

    def get_status(self) -> dict[str, Any]:
        total = self.equity_curve[-1] if self.equity_curve else self.cash
        peak = self.peak_value
        drawdown = round((total - peak) / peak * 100, 1) if peak > 0 else 0.0

        return {
            "cash": round(self.cash, 4),
            "holdings_count": len(self.holdings),
            "total_value": round(total, 4),
            "peak_value": round(peak, 4),
            "drawdown_pct": drawdown,
            "total_exposure": round(1 - self.cash / total, 2) if total > 0 else 0,
        }
