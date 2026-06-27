"""
policy.py — v11 自适应策略大脑
=================================
根据市场反馈持续调整决策参数
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v11.policy")


class Policy:
    """自适应策略 — 参数由 Learner 动态调整"""

    def __init__(self):
        self.aggression = 0.5       # 攻击性 (0=保守, 1=激进)
        self.risk_aversion = 0.5    # 风险厌恶 (0=无惧, 1=极度厌恶)
        self.resonance_weight = 0.5 # v6共振权重
        self.leader_weight = 0.5    # v3龙头权重
        self.max_exposure = 0.70    # 最大仓位 (动态调整)
        self.min_confidence = 0.5   # 最低信号置信度

    def decide(self, state: dict[str, Any]) -> str:
        """
        根据当前状态 + 策略参数做出决策。

        state: {resonance_score, leader_score, regime, drawdown_pct, volatility}

        Returns: BUY / SELL / HOLD
        """
        resonance = state.get("resonance_score", 0)
        leader = state.get("leader_score", 0)
        regime = state.get("regime", "neutral")
        drawdown = abs(state.get("drawdown_pct", 0))

        # 风险厌恶过高 → 保守
        if drawdown > 10 * self.risk_aversion:
            return "HOLD"

        # 退潮/恐慌 → 卖出或持有
        if regime in ("downtrend_market", "crash_market"):
            return "SELL" if leader < 0.3 else "HOLD"

        # 共振 + 龙头 加权判断
        weighted = (resonance * self.resonance_weight +
                    leader * self.leader_weight)

        if weighted > 0.6 * self.aggression:
            return "BUY"
        elif weighted > 0.4:
            return "HOLD"
        else:
            return "SELL"

    def adjust(self, field: str, delta: float) -> None:
        """调整单个参数 (带边界限制)"""
        current = getattr(self, field, 0.5)
        new_val = max(0.0, min(1.0, current + delta))
        setattr(self, field, round(new_val, 3))
        logger.debug(f"Policy.{field}: {current:.3f} → {new_val:.3f} (Δ{delta:+.3f})")

    def get_weights(self) -> dict[str, Any]:
        return {
            "aggression": self.aggression,
            "risk_aversion": self.risk_aversion,
            "resonance_weight": self.resonance_weight,
            "leader_weight": self.leader_weight,
            "max_exposure": self.max_exposure,
            "min_confidence": self.min_confidence,
        }

    def save(self, path: str = "state/v11_policy.json") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.get_weights(), f, indent=2)

    def load(self, path: str = "state/v11_policy.json") -> bool:
        fp = Path(path)
        if not fp.exists():
            return False
        try:
            with open(fp) as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            return True
        except (json.JSONDecodeError, OSError):
            return False
