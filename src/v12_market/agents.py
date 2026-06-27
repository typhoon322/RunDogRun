"""
agents.py — v12 多Agent市场博弈
==================================
4种市场参与者: 趋势 / 均值回归 / 情绪 / 我方(v11)
"""
import random
from typing import Any


class TrendAgent:
    """趋势交易者 — 追涨杀跌, 占市场 30%"""

    def __init__(self, sensitivity: float = 0.6):
        self.sensitivity = sensitivity
        self.capital = 1.0
        self.position = 0

    def act(self, state: dict[str, Any]) -> str:
        trend = state.get("price_trend", 0)  # 近期涨跌幅
        momentum = state.get("momentum", 0)

        if trend > 0.3 and momentum > 0:
            return "BUY" if random.random() < self.sensitivity else "HOLD"
        elif trend < -0.3:
            return "SELL" if random.random() < self.sensitivity else "HOLD"
        return "HOLD"

    @property
    def name(self) -> str:
        return "trend_trader"


class MeanReversionAgent:
    """均值回归交易者 — 高抛低吸, 占市场 25%"""

    def __init__(self, threshold: float = 1.5):
        self.threshold = threshold
        self.capital = 1.0
        self.position = 0

    def act(self, state: dict[str, Any]) -> str:
        zscore = state.get("zscore", 0)  # 偏离均值的标准差

        if zscore > self.threshold:
            return "SELL"  # 超买 → 卖出
        elif zscore < -self.threshold:
            return "BUY"   # 超卖 → 买入
        return "HOLD"

    @property
    def name(self) -> str:
        return "mean_reversion"


class SentimentAgent:
    """情绪交易者 — 恐惧/贪婪驱动, 占市场 20%"""

    def __init__(self, fear_threshold: float = 0.7, greed_threshold: float = 0.7):
        self.fear_threshold = fear_threshold
        self.greed_threshold = greed_threshold
        self.capital = 1.0
        self.position = 0

    def act(self, state: dict[str, Any]) -> str:
        fear = state.get("fear_index", 0.5)
        greed = state.get("greed_index", 0.5)

        if fear > self.fear_threshold:
            return "SELL"  # 恐慌 → 抛售
        elif greed > self.greed_threshold:
            return "BUY"   # 贪婪 → 追高
        return "HOLD"

    @property
    def name(self) -> str:
        return "sentiment"


class NoiseAgent:
    """噪声交易者 — 随机行为, 占市场 15% (模拟散户)"""

    def act(self, state: dict[str, Any]) -> str:
        return random.choice(["BUY", "SELL", "HOLD"])

    @property
    def name(self) -> str:
        return "noise"


class AgentFactory:
    """创建完整的市场Agent群体"""

    @staticmethod
    def create_population(v11_agent=None) -> list:
        agents = [
            TrendAgent(sensitivity=0.6),
            TrendAgent(sensitivity=0.4),
            MeanReversionAgent(threshold=1.5),
            MeanReversionAgent(threshold=1.0),
            SentimentAgent(fear_threshold=0.7, greed_threshold=0.7),
            NoiseAgent(),
            NoiseAgent(),
        ]
        if v11_agent is not None:
            agents.append(v11_agent)
        return agents

    @staticmethod
    def action_summary(actions: list[str]) -> dict[str, int]:
        """统计买卖压力"""
        return {
            "buy_pressure": actions.count("BUY"),
            "sell_pressure": actions.count("SELL"),
            "hold_count": actions.count("HOLD"),
            "total": len(actions),
        }
