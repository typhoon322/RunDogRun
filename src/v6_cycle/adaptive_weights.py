"""
adaptive_weights.py — v6 自适应权重
====================================
根据共振分数动态调整 v1-v4 系统权重
"""
import logging
from typing import Any

logger = logging.getLogger("quant.v6.adaptive_weights")


RESONANCE_WEIGHTS = {
    "triple_align": {
        "v1_signal": 1.2,
        "v3_leader": 1.4,
        "v4_risk_limit": 1.0,
        "description": "三级共振, 全力做多",
    },
    "dual_align": {
        "v1_signal": 1.1,
        "v3_leader": 1.1,
        "v4_risk_limit": 0.85,
        "description": "两级共振, 正常偏多",
    },
    "single_align": {
        "v1_signal": 0.7,
        "v3_leader": 0.7,
        "v4_risk_limit": 0.55,
        "description": "单周期, 轻仓试探",
    },
    "conflict": {
        "v1_signal": 0.0,
        "v3_leader": 0.0,
        "v4_risk_limit": 0.15,
        "description": "周期冲突, 禁止交易",
    },
    "flat": {
        "v1_signal": 0.3,
        "v3_leader": 0.3,
        "v4_risk_limit": 0.30,
        "description": "全横盘, 观望",
    },
}


def compute_adaptive_weights(
    resonance: dict[str, Any],
    market_regime: str = "neutral",
) -> dict[str, Any]:
    """
    综合共振 + 市场状态, 输出最终权重。

    Args:
        resonance: 共振评分结果
        market_regime: v5市场状态

    Returns:
        {v1_signal, v3_leader, v4_risk_limit, v6_resonance_weight, description}
    """
    alignment = resonance.get("overall", {}).get("label", "conflict")
    weights = RESONANCE_WEIGHTS.get(alignment, RESONANCE_WEIGHTS["conflict"]).copy()

    # 市场状态叠加修正
    regime_modifier = {
        "trend_market": 1.0,
        "range_market": 0.85,
        "downtrend_market": 0.6,
        "crash_market": 0.3,
    }.get(market_regime, 0.8)

    weights["v1_signal"] = round(weights["v1_signal"] * regime_modifier, 2)
    weights["v3_leader"] = round(weights["v3_leader"] * regime_modifier, 2)

    # 共振权重: 用于整体系统信号放大/缩小
    resonance_weight = weights["v3_leader"]

    logger.info(f"权重: v1={weights['v1_signal']}, v3={weights['v3_leader']}, "
                f"risk={weights['v4_risk_limit']}, resonance={resonance_weight}")

    return {
        "v1_signal": weights["v1_signal"],
        "v3_leader": weights["v3_leader"],
        "v4_risk_limit": weights["v4_risk_limit"],
        "v6_resonance_weight": resonance_weight,
        "alignment": alignment,
        "regime_modifier": regime_modifier,
        "description": weights["description"],
    }
