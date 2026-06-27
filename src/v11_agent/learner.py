"""
learner.py — v11 在线学习引擎
================================
根据交易奖励反向调整策略参数
"""
import logging
from typing import Any

from src.v11_agent.policy import Policy

logger = logging.getLogger("quant.v11.learner")

# 学习率配置
LEARNING_RATES = {
    "win":  {"aggression": 0.01, "resonance_weight": 0.02, "leader_weight": 0.02},
    "lose": {"aggression": -0.02, "risk_aversion": 0.02, "resonance_weight": -0.01},
    "big_win":  {"aggression": 0.03, "max_exposure": 0.02, "leader_weight": 0.03},
    "big_lose": {"aggression": -0.04, "max_exposure": -0.03, "risk_aversion": 0.04},
}


class Learner:
    """在线策略学习器 — 根据 reward 调整 Policy 参数"""

    def __init__(self, policy: Policy):
        self.policy = policy
        self.learning_steps = 0
        self.total_reward = 0.0
        self.reward_history: list[float] = []

    def update(self, reward: float, trade_pnl: float) -> dict[str, Any]:
        """
        根据奖励信号更新策略。

        Args:
            reward: 计算出的奖励值
            trade_pnl: 实际交易盈亏%

        Returns:
            本次调整记录
        """
        adjustments = {}

        if reward > 1.0:
            rules = LEARNING_RATES["big_win"]
            trigger = "big_win"
        elif reward > 0:
            rules = LEARNING_RATES["win"]
            trigger = "win"
        elif reward < -1.0:
            rules = LEARNING_RATES["big_lose"]
            trigger = "big_lose"
        else:
            rules = LEARNING_RATES["lose"]
            trigger = "lose"

        for field, delta in rules.items():
            old = getattr(self.policy, field, 0.5)
            self.policy.adjust(field, delta)
            new = getattr(self.policy, field, 0.5)
            if old != new:
                adjustments[field] = {"from": old, "to": new, "delta": delta}

        self.learning_steps += 1
        self.total_reward += reward
        self.reward_history.append(reward)

        if self.learning_steps % 10 == 0:
            avg = sum(self.reward_history[-10:]) / min(10, len(self.reward_history))
            logger.info(f"Learner step={self.learning_steps}, "
                       f"avg_reward={avg:.2f}, trigger={trigger}")

        return {
            "step": self.learning_steps,
            "trigger": trigger,
            "reward": reward,
            "trade_pnl": trade_pnl,
            "adjustments": adjustments,
        }

    def get_status(self) -> dict[str, Any]:
        recent = self.reward_history[-20:]
        avg = sum(recent) / len(recent) if recent else 0
        return {
            "learning_steps": self.learning_steps,
            "total_reward": round(self.total_reward, 2),
            "avg_reward_20": round(avg, 2),
            "policy": self.policy.get_weights(),
        }
