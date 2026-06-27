"""
v2_final/strategy/signal.py — v2.1 信号生成 (动态置信度)
===========================================================
共振判断 + 动态置信度 + 自适应
"""
from typing import Any


def generate_signal(
    leaders: list[dict],
    sectors: list[dict],
    portfolio_exposure: float = 0.0,
    drawdown_status: str = "OK",
    stats: dict | None = None,
) -> dict[str, Any]:
    """v2.2 动态信号生成"""

    strong_sectors = [s for s in sectors if s.get("level") == "strong"]

    if not leaders:
        return {"action": "HOLD", "reason": "无候选"}

    if not strong_sectors:
        return {"action": "HOLD", "reason": "无强板块"}

    top_leader = leaders[0]
    top_sector = strong_sectors[0]

    # 基础置信度
    if top_leader["score"] > 8 and top_sector["strength"] > 5:
        confidence = 0.80
        action = "BUY"
    elif top_leader["score"] > 5:
        confidence = 0.65
        action = "BUY"
    elif top_leader["score"] > 3:
        confidence = 0.55
        action = "BUY"
    else:
        confidence = 0.45
        action = "HOLD"

    # v2.2 回撤降风险
    if drawdown_status == "REDUCE_RISK":
        confidence *= 0.7
    elif drawdown_status == "STOP_TRADING":
        action = "HOLD"
        confidence = 0

    # v2.2 胜率自适应
    if stats:
        win_rate = stats.get("win_rate", 0.5)
        if win_rate < 0.45:
            confidence *= 0.8
        elif win_rate > 0.6:
            confidence *= 1.1

    # 满仓不加
    if portfolio_exposure >= 0.6 and action == "BUY":
        action = "HOLD"

    return {
        "action": action,
        "stock_code": top_leader["code"] if action == "BUY" else "",
        "stock_name": top_leader.get("name", ""),
        "price": top_leader.get("price", 0),
        "score": top_leader.get("score", 0),
        "confidence": round(min(0.95, confidence), 2),
        "sector": top_sector.get("name", ""),
        "drawdown_status": drawdown_status,
        "reason": (
            f"{top_sector['name']}({top_sector['strength']:.1f}) + "
            f"{top_leader['name']}({top_leader['score']:.1f})"
        ),
    }
