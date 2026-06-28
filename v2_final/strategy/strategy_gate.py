"""
v2_final/strategy/strategy_gate.py — v2.5 策略可信度门控
=============================================================
评分: win_rate>55% + max_dd<8% + total_return>0 → 0-3
门控: score >= 2 → 启用交易
"""
import logging
from typing import Any

logger = logging.getLogger("v2.strategy_gate")


def score_strategy(stats: dict[str, Any]) -> int:
    """
    策略可信度评分 (0-3)。

    每满足一个条件 +1:
      1. 胜率 > 55%
      2. 回撤 < 8%
      3. 总收益 > 0
    """
    score = 0
    reasons = []

    if stats.get("win_rate", 0) > 0.55:
        score += 1
        reasons.append("胜率>55%")

    max_dd = abs(stats.get("max_drawdown", 99))
    if max_dd < 8:
        score += 1
        reasons.append("回撤<8%")

    if stats.get("total_return", 0) > 0:
        score += 1
        reasons.append("收益>0")

    logger.info(f"策略评分: {score}/3 ({', '.join(reasons)})")
    return score


def should_trade(score: int) -> bool:
    """门控: 评分 >= 2 才启用交易"""
    return score >= 2


def get_verdict(stats: dict[str, Any]) -> dict[str, Any]:
    """
    完整判定: 打分 + 门控 + 建议。

    Returns:
        {score, should_trade, verdict, reasons}
    """
    score = score_strategy(stats)
    trade = should_trade(score)

    if trade:
        verdict = "TRADE"
    elif score == 1:
        verdict = "SKIP — 策略质量不足"
    else:
        verdict = "SKIP — 策略不可用"

    return {
        "score": score,
        "should_trade": trade,
        "verdict": verdict,
        "stats": {
            "win_rate": stats.get("win_rate", 0),
            "max_drawdown": stats.get("max_drawdown", 0),
            "total_return": stats.get("total_return", 0),
        },
    }
