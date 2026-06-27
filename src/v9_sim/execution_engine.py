"""
execution_engine.py — v9 模拟执行引擎
=========================================
仿真: 延迟 + 滑点 + 成交率 + 成本模型
"""
import random
import logging
from typing import Any

logger = logging.getLogger("quant.v9.execution")


class SimulationEngine:
    """模拟交易执行 — 真实成本建模"""

    def __init__(self, slippage_bps: float = 3.0, latency_range: tuple = (0.3, 1.5),
                 fill_rate: float = 0.95):
        self.slippage_bps = slippage_bps       # 滑点 (基点)
        self.latency_range = latency_range     # 延迟范围 (秒)
        self.fill_rate = fill_rate             # 成交率
        self.execution_log: list[dict] = []

    def execute(self, order: dict, market_price: float) -> dict[str, Any]:
        """
        执行模拟交易。

        Args:
            order: {side: BUY/SELL, size: float, price: float}
            market_price: 当前市价

        Returns:
            {mode, fill_price, latency, filled, cost_bps}
        """
        # 延迟
        latency = round(random.uniform(*self.latency_range), 2)

        # 滑点 (买单加滑点, 卖单减滑点)
        slippage_pct = random.uniform(0.001, self.slippage_bps / 10000)
        if order["side"] == "BUY":
            fill_price = round(market_price * (1 + slippage_pct), 3)
        else:
            fill_price = round(market_price * (1 - slippage_pct), 3)

        # 成交判断
        filled = random.random() < self.fill_rate

        # 记录
        result = {
            "mode": "simulation",
            "order_side": order["side"],
            "order_price": order.get("price", market_price),
            "market_price": market_price,
            "fill_price": fill_price if filled else 0,
            "latency": latency,
            "slippage_bps": round(slippage_pct * 10000, 1),
            "filled": filled,
        }
        self.execution_log.append(result)
        return result

    def get_metrics(self) -> dict[str, Any]:
        """执行质量评估"""
        if not self.execution_log:
            return {"mode": "simulation", "trades": 0}

        filled = [r for r in self.execution_log if r["filled"]]
        fill_rate = len(filled) / len(self.execution_log)

        avg_slippage = sum(r["slippage_bps"] for r in self.execution_log) / len(self.execution_log)
        avg_latency = sum(r["latency"] for r in self.execution_log) / len(self.execution_log)

        return {
            "mode": "simulation",
            "total_orders": len(self.execution_log),
            "filled_orders": len(filled),
            "fill_rate": round(fill_rate, 2),
            "avg_slippage_bps": round(avg_slippage, 1),
            "avg_latency_s": round(avg_latency, 2),
        }
