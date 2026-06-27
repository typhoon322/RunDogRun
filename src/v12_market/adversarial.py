"""
adversarial.py — v12 对抗学习训练器
=====================================
v11 Agent vs 市场群体 — 在博弈中进化
"""
import logging
from typing import Any

from src.v12_market.agents import AgentFactory
from src.v12_market.market_sim import MarketSimulator

logger = logging.getLogger("quant.v12.adversarial")


class AdversarialTrainer:
    """对抗学习训练器 — v11 在市场模拟中对抗训练"""

    def __init__(self, v11_agent=None, n_agents: int = 7, initial_price: float = 100.0):
        # 创建市场参与者 (不含v11)
        self.market_agents = AgentFactory.create_population()
        self.v11_agent = v11_agent

        # 市场模拟器
        self.simulator = MarketSimulator(
            agents=self.market_agents,
            initial_price=initial_price,
            volatility=0.3,
        )

        # v11 性能追踪
        self.v11_pnl = 0.0
        self.v11_trades = 0
        self.v11_wins = 0
        self.episode_history: list[dict] = []

    def add_v11_agent(self, agent) -> None:
        """将 v11 Agent 加入市场"""
        self.v11_agent = agent
        if agent not in self.market_agents:
            self.market_agents.append(agent)

    def run_episode(self, steps: int = 100) -> dict[str, Any]:
        """运行一个对抗训练 episode"""
        v11_actions = []
        prices = [self.simulator.price]

        for _ in range(steps):
            state = self.simulator._derive_state()

            # v11 决策 + 添加共振/龙头数据
            v11_state = {
                **state,
                "resonance_score": 0.5 + state.get("price_trend", 0) / 10,
                "leader_score": 0.5 + state.get("momentum", 0) / 10,
                "regime": self._trend_to_regime(state.get("price_trend", 0)),
                "drawdown_pct": 0,
            }

            if self.v11_agent:
                v11_action = self.v11_agent.decide(v11_state)
                v11_actions.append(v11_action)

            result = self.simulator.step(state)
            prices.append(result["price"])

        # 评估 v11
        if v11_actions and len(prices) >= 2:
            v11_result = self._evaluate_v11(v11_actions, prices)
        else:
            v11_result = {"pnl": 0, "win_rate": 0}

        summary = self.simulator.summary()
        self.episode_history.append({**summary, "v11": v11_result})

        return {
            "market": summary,
            "v11_performance": v11_result,
            "episode": self.episode_history[-1],
        }

    def _evaluate_v11(self, actions: list[str], prices: list[float]) -> dict[str, Any]:
        """评估 v11 决策质量 — 计算模拟PnL"""
        position = 0
        entry_price = 0
        pnl = 0
        wins = 0
        trades = 0

        for i, action in enumerate(actions):
            if i >= len(prices) - 1:
                break

            if action == "BUY" and position == 0:
                position = 1
                entry_price = prices[i]
                trades += 1
            elif action == "SELL" and position == 1:
                trade_pnl = (prices[i] - entry_price) / entry_price if entry_price > 0 else 0
                pnl += trade_pnl
                if trade_pnl > 0:
                    wins += 1
                position = 0

        # 未平仓按最后价格结算
        if position == 1 and prices:
            trade_pnl = (prices[-1] - entry_price) / entry_price if entry_price > 0 else 0
            pnl += trade_pnl
            if trade_pnl > 0:
                wins += 1

        return {
            "pnl_pct": round(pnl * 100, 2),
            "trades": trades,
            "wins": wins,
            "win_rate": round(wins / trades, 2) if trades > 0 else 0,
            "quality": "good" if pnl > 0.05 else ("neutral" if pnl > -0.02 else "poor"),
        }

    @staticmethod
    def _trend_to_regime(trend: float) -> str:
        if trend > 1:
            return "trend_market"
        elif trend > -0.5:
            return "range_market"
        elif trend > -2:
            return "downtrend_market"
        return "crash_market"
