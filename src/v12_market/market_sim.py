"""
market_sim.py — v12 市场模拟引擎
===================================
价格由 买方压力 - 卖方压力 + 噪声 + 流动性 驱动
"""
import logging
import random
from typing import Any

logger = logging.getLogger("quant.v12.market")


class MarketSimulator:
    """多Agent市场模拟器"""

    def __init__(self, agents: list, initial_price: float = 100.0,
                 volatility: float = 0.3, liquidity: float = 0.05):
        self.agents = agents
        self.price = initial_price
        self.price_history: list[float] = [initial_price]
        self.volatility = volatility        # 基础波动率
        self.liquidity = liquidity          # 流动性因子 (越小越容易推动价格)
        self.step_count = 0

    def step(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        执行一个市场周期。

        Returns:
            {price, actions, pressure, state}
        """
        if state is None:
            state = self._derive_state()

        # 收集所有Agent动作
        actions = [agent.act(state) for agent in self.agents]
        buys = actions.count("BUY")
        sells = actions.count("SELL")

        # 价格变化 = (买方压力 - 卖方压力) × 流动性因子 + 噪声
        pressure = (buys - sells) * self.liquidity
        noise = random.gauss(0, self.volatility * 0.3)
        price_change = pressure + noise

        self.price = round(self.price + price_change, 3)
        self.price = max(1.0, self.price)
        self.price_history.append(self.price)
        self.step_count += 1

        return {
            "price": self.price,
            "price_change": round(price_change, 3),
            "pressure": {"buy": buys, "sell": sells, "net": buys - sells},
            "actions": actions,
            "state": state,
        }

    def _derive_state(self) -> dict[str, Any]:
        """从价格历史推导当前市场状态"""
        if len(self.price_history) < 5:
            return {"price_trend": 0, "momentum": 0, "zscore": 0,
                    "fear_index": 0.5, "greed_index": 0.5}

        prices = self.price_history
        recent = prices[-5:]
        trend = (prices[-1] - prices[-5]) / prices[-5] * 100 if prices[-5] > 0 else 0

        # zscore: 当前价格偏离20日均值的标准差
        window = prices[-20:] if len(prices) >= 20 else prices
        avg = sum(window) / len(window)
        var = sum((p - avg) ** 2 for p in window) / len(window)
        sigma = var ** 0.5 if var > 0 else 1
        zscore = (prices[-1] - avg) / sigma

        # 恐惧贪婪指数 (基于价格变化)
        recent_returns = [(prices[i] - prices[i-1]) / prices[i-1]
                         for i in range(-min(5, len(prices)-1), 0)]
        avg_return = sum(recent_returns) / len(recent_returns) if recent_returns else 0
        fear = max(0, min(1, -avg_return * 20 + 0.5))
        greed = max(0, min(1, avg_return * 20 + 0.5))

        return {
            "price_trend": round(trend, 2),
            "momentum": round(avg_return * 100, 2),
            "zscore": round(zscore, 2),
            "fear_index": round(fear, 2),
            "greed_index": round(greed, 2),
        }

    def run_episode(self, steps: int = 100) -> list[dict[str, Any]]:
        """运行一个完整 episode"""
        history = []
        for _ in range(steps):
            result = self.step()
            history.append(result)
        return history

    def summary(self) -> dict[str, Any]:
        prices = self.price_history
        if len(prices) < 2:
            return {"steps": self.step_count, "current_price": self.price}
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        avg_return = sum(returns) / len(returns)
        vol = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
        return {
            "steps": self.step_count,
            "initial_price": prices[0],
            "final_price": prices[-1],
            "total_return_pct": round((prices[-1] / prices[0] - 1) * 100, 2),
            "volatility": round(vol * 100, 2),
            "max_price": max(prices),
            "min_price": min(prices),
        }
