"""
agent.py — v11 自进化交易 Agent (主入口)
===========================================
整合: Policy + Reward + Learner + Experience

闭环: Market → Signal → Execution → PnL → Reward → Learn → Policy → Market
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.v11_agent.policy import Policy
from src.v11_agent.reward import compute_reward, compute_trade_pnl
from src.v11_agent.learner import Learner
from src.v11_agent.experience import ExperienceBuffer

logger = logging.getLogger("quant.v11.agent")


class SelfEvolvingAgent:
    """自进化交易 Agent — 市场反馈闭环"""

    def __init__(self, mode: str = "sim"):
        self.policy = Policy()
        self.learner = Learner(self.policy)
        self.experience = ExperienceBuffer(capacity=500)
        self.mode = mode

        # 尝试加载已有模型
        if self.policy.load():
            logger.info("已加载已有策略")
        if self.experience.load():
            logger.info(f"已加载经验池: {len(self.experience.memory)} 条")

    def decide(self, state: dict[str, Any]) -> str:
        """基于当前状态 + 策略参数做决策"""
        return self.policy.decide(state)

    def feedback(self, trade: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
        """
        交易结果反馈 — 驱动学习闭环。

        Args:
            trade: {action, entry_price, exit_price, side, hold_days}
            portfolio: {drawdown_pct, total_exposure, daily_trades}

        Returns:
            学习结果
        """
        # 1. 计算 PnL
        pnl = compute_trade_pnl(
            trade.get("entry_price", 0),
            trade.get("exit_price", 0),
            trade.get("side", trade.get("action", "BUY")),
        )
        trade["pnl_pct"] = pnl

        # 2. 计算奖励
        reward = compute_reward(trade, portfolio)

        # 3. 存入经验池
        self.experience.add({
            "date": datetime.now().isoformat(),
            "action": trade.get("action", ""),
            "entry_price": trade.get("entry_price", 0),
            "exit_price": trade.get("exit_price", 0),
            "pnl_pct": pnl,
            "reward": reward,
            "state": trade.get("state", {}),
        })

        # 4. 学习更新
        learn_result = self.learner.update(reward, pnl)

        # 5. 持久化
        if self.learner.learning_steps % 5 == 0:
            self.policy.save()
            self.experience.save()

        return {
            "pnl_pct": pnl,
            "reward": reward,
            "learning": learn_result,
            "stats": self.experience.recent_stats(),
        }

    def get_status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "learning": self.learner.get_status(),
            "experience": self.experience.recent_stats(),
            "policy": self.policy.get_weights(),
        }

    def run_cycle(self, state: dict[str, Any], portfolio: dict[str, Any],
                  market_price: float) -> dict[str, Any]:
        """
        运行一次完整决策→执行→学习 周期。

        Returns:
            {decision, execution, feedback, policy_state}
        """
        # 决策
        action = self.decide(state)

        # 模拟执行
        execution = {
            "action": action,
            "side": action if action in ("BUY", "SELL") else "HOLD",
            "entry_price": market_price,
            "exit_price": market_price,  # 当日收盘
            "filled": action != "HOLD",
        }

        # 反馈学习
        if execution["filled"]:
            fb = self.feedback(execution, portfolio)
        else:
            fb = {"pnl_pct": 0, "reward": 0}

        return {
            "date": datetime.now().isoformat(),
            "agent_state": "learning" if self.learner.learning_steps > 0 else "initializing",
            "decision": {"action": action, "confidence": self.policy.aggression},
            "execution": execution,
            "feedback": fb,
            "policy": self.policy.get_weights(),
            "learning_status": self.learner.get_status(),
        }
