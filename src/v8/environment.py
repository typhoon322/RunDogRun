"""
rl_agent.py — v8 强化学习交易Agent
===================================
Q-Learning Agent: 状态 → 动作 → 奖励 → 学习
不依赖深度学习框架, 纯 Python + 数学实现
"""
import json
import logging
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v8.rl-agent")


# ── 状态定义 ──
STATES = [
    "strong_bull",      # 强牛市 + 高共振
    "mild_bull",        # 温和看涨
    "neutral",          # 中性
    "mild_bear",        # 温和看跌
    "strong_bear",      # 强熊市
]

# ── 动作空间 ──
ACTIONS = [
    "BUY",              # 开仓
    "HOLD",             # 持有
    "SELL",             # 卖出
    "INCREASE",         # 加仓
    "DECREASE",         # 减仓
    "NO_ACTION",        # 观望
]

# ── 默认 Q-Table ──
# 初始化: 每个 (state, action) 对 Q=0
# 温和偏多倾向


class QLearningAgent:
    """Q-Learning 交易智能体"""

    def __init__(self, alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.15):
        self.alpha = alpha       # 学习率
        self.gamma = gamma       # 折扣因子
        self.epsilon = epsilon   # 探索率
        self.q_table: dict[str, dict[str, float]] = defaultdict(
            lambda: {a: random.uniform(-0.01, 0.01) for a in ACTIONS}
        )
        self.episode_rewards: list[float] = []
        self.train_steps = 0

    def encode_state(self, regime: str, resonance_label: str,
                     cycle_stage: str = "", drawdown_pct: float = 0.0) -> str:
        """
        将市场特征编码为离散状态。

        状态空间: 5个离散状态
        """
        # 5分制: 趋势市=4, 震荡=3, 退潮=1, 恐慌=0
        regime_score = {
            "trend_market": 4, "range_market": 3,
            "downtrend_market": 1, "crash_market": 0,
            "neutral": 2,
        }.get(regime, 2)

        # 共振加分
        resonance_bonus = {
            "strong_alignment": 1.0, "triple_align": 1.0,
            "moderate": 0.5, "dual_align": 0.5,
            "single_align": 0.0, "weak": 0.0,
            "conflict": -1.0, "flat": -0.5,
        }.get(resonance_label, 0)

        # 回撤惩罚
        dd_penalty = 0 if drawdown_pct > -3 else (-1 if drawdown_pct > -8 else -2)

        total = regime_score + resonance_bonus + dd_penalty

        if total >= 4.5:
            return "strong_bull"
        elif total >= 3:
            return "mild_bull"
        elif total >= 1.5:
            return "neutral"
        elif total >= 0:
            return "mild_bear"
        else:
            return "strong_bear"

    def choose_action(self, state: str, explore: bool = True) -> str:
        """ε-greedy 动作选择"""
        if explore and random.random() < self.epsilon:
            return random.choice(ACTIONS)
        q_values = self.q_table[state]
        return max(q_values, key=q_values.get)

    def learn(self, state: str, action: str, reward: float, next_state: str) -> None:
        """Q-Learning 更新"""
        best_next = max(self.q_table[next_state].values())
        current = self.q_table[state][action]
        self.q_table[state][action] = current + self.alpha * (
            reward + self.gamma * best_next - current
        )
        self.train_steps += 1

    def compute_reward(self, action: str, trade_return: float, regime: str,
                       drawdown: float, overtrade: bool = False) -> float:
        """
        奖励函数:

        Reward = Profit - DD_Penalty + Alignment_Bonus - Overtrade_Penalty
        """
        # 收益奖励
        profit_reward = min(2.0, max(-2.0, trade_return / 5))

        # 回撤惩罚
        dd_penalty = abs(drawdown / 100) * 2 if drawdown < -5 else 0

        # 对齐奖励 (市场状态匹配动作)
        alignment = 0.0
        if regime in ("trend_market",) and action in ("BUY", "INCREASE"):
            alignment = 0.5
        elif regime in ("downtrend_market", "crash_market") and action in ("SELL", "DECREASE"):
            alignment = 0.5
        elif action == "NO_ACTION" and regime in ("neutral",):
            alignment = 0.3

        # 过度交易惩罚
        overtrade_penalty = -1.0 if overtrade else 0.0

        return round(profit_reward - dd_penalty + alignment + overtrade_penalty, 2)

    def train_episode(self, historical_data: list[dict]) -> float:
        """在历史数据上训练一个 episode"""
        total_reward = 0.0
        state = "neutral"
        position = 0.0  # 0=空仓, 0.3=30%仓

        for step in historical_data:
            action = self.choose_action(state)
            trade_return = step.get("return", 0)
            regime = step.get("regime", "neutral")
            resonance = step.get("resonance", "flat")
            dd = step.get("drawdown", 0)

            # 模拟仓位变化
            if action == "BUY" and position < 0.3:
                position += 0.1
            elif action == "SELL" and position > 0:
                position = 0
            elif action == "INCREASE" and position < 0.5:
                position += 0.1
            elif action == "DECREASE" and position > 0:
                position -= 0.1

            overtrade = False
            if action in ("BUY", "SELL") and abs(step.get("return", 0)) < 0.5:
                overtrade = True  # 小波动频繁交易

            reward = self.compute_reward(action, trade_return, regime, dd, overtrade)
            next_state = self.encode_state(regime, resonance,
                                          step.get("cycle_stage", ""), dd)

            self.learn(state, action, reward, next_state)
            total_reward += reward
            state = next_state

        self.episode_rewards.append(total_reward)
        return total_reward

    def get_policy(self) -> dict[str, Any]:
        """导出当前策略"""
        policy = {}
        for state in STATES:
            q_values = self.q_table[state]
            best_action = max(q_values, key=q_values.get)
            policy[state] = {
                "best_action": best_action,
                "confidence": round(
                    1 / (1 + math.exp(-q_values[best_action])), 2
                ),
                "q_values": {a: round(v, 3) for a, v in sorted(q_values.items(), key=lambda x: -x[1])[:3]},
            }

        return {
            "policy": policy,
            "risk_preference": round(0.5 + self.epsilon * 2, 2),
            "aggression_level": round(self._aggression_level(), 2),
            "train_steps": self.train_steps,
            "avg_reward": round(sum(self.episode_rewards[-10:]) / max(1, len(self.episode_rewards[-10:])), 2) if self.episode_rewards else 0,
        }

    def _aggression_level(self) -> float:
        """计算攻击性水平 (BUY+INCREASE 占比)"""
        total = sum(sum(abs(v) for v in q.values()) for q in self.q_table.values())
        if total < 0.001:
            return 0.5
        aggressive = sum(
            self.q_table[s].get("BUY", 0) + self.q_table[s].get("INCREASE", 0)
            for s in STATES
        )
        return round(max(0.1, min(0.9, (aggressive / max(0.001, total)) * 2)), 2)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "q_table": {s: dict(a) for s, a in self.q_table.items()},
                "train_steps": self.train_steps,
                "epsilon": self.epsilon,
                "alpha": self.alpha,
                "gamma": self.gamma,
            }, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        try:
            with open(p) as f:
                data = json.load(f)
            for s, actions in data.get("q_table", {}).items():
                self.q_table[s] = actions
            self.train_steps = data.get("train_steps", 0)
            self.epsilon = data.get("epsilon", 0.15)
            self.alpha = data.get("alpha", 0.1)
            self.gamma = data.get("gamma", 0.9)
            return True
        except (json.JSONDecodeError, OSError):
            return False


def train_agent(
    data_dir: str = "data",
    episodes: int = 50,
    model_path: str = "state/rl_agent.json",
) -> dict[str, Any]:
    """
    训练 RL 交易 Agent。

    从历史数据文件构建训练集，跑 N 个 episode。
    """
    import glob
    agent = QLearningAgent()

    # 加载已有模型 (增量训练)
    if agent.load(model_path):
        logger.info(f"加载已有模型: {agent.train_steps} 步")

    # 收集历史数据
    files = sorted(glob.glob(f"{data_dir}/????-??-??.json"))
    if len(files) < 5:
        logger.warning("历史数据不足, 跳过训练")
        return {"error": "insufficient_data", "agent": agent.get_policy()}

    training_data = []
    for fp in files[-60:]:  # 最近60天
        try:
            with open(fp) as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        regime = ""
        regime_path = Path(fp.replace(".json", "_regime.json"))
        if regime_path.exists():
            with open(regime_path) as f:
                rd = json.load(f)
            regime = rd.get("market_regime", "neutral")

        resonance_label = ""
        res_path = Path(fp.replace(".json", "_resonance.json"))
        if res_path.exists():
            with open(res_path) as f:
                rd = json.load(f)
            resonance_label = rd.get("resonance", {}).get("label", "flat")

        market = d.get("market", {})
        training_data.append({
            "date": d.get("date", ""),
            "return": market.get("overall_return", 0),
            "regime": regime or d.get("market_regime", "neutral"),
            "resonance": resonance_label,
            "drawdown": 0,  # 简化
        })

    if len(training_data) < 10:
        logger.warning("训练数据不足")
        return {"error": "insufficient_training_data", "agent": agent.get_policy()}

    # 训练
    logger.info(f"开始训练: {len(training_data)} 条数据, {episodes} 轮")
    for ep in range(episodes):
        reward = agent.train_episode(training_data)
        if ep % 10 == 0:
            logger.debug(f"  Episode {ep}: reward={reward:.2f}, ε={agent.epsilon:.2f}")

    # 保存模型
    import os
    os.makedirs("state", exist_ok=True)
    agent.save(model_path)

    policy = agent.get_policy()
    logger.info(f"训练完成: {agent.train_steps}步, avg_reward={policy['avg_reward']}")

    return {
        "agent_state": "trained",
        "episodes": episodes,
        "train_samples": len(training_data),
        "policy": policy,
    }
