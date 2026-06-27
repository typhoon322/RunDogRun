"""
v2_final/strategy/signal.py — 信号生成
=========================================
核心规则: 强板块 + 强个股 → BUY
"""
from typing import Any


def generate_signal(
    leaders: list[dict],
    sectors: list[dict],
    portfolio_exposure: float = 0.0,
) -> dict[str, Any]:
    """
    生成交易信号。

    规则:
      1. 至少1个强板块
      2. 龙头动量>5% 或 强板块>2%
      3. 板块+个股共振 → 高置信度
    """
    strong_sectors = [s for s in sectors if s.get("level") == "strong"]

    if not leaders:
        return {"action": "HOLD", "reason": "无龙头候选"}

    if not strong_sectors:
        return {"action": "HOLD", "reason": "无强板块"}

    top_leader = leaders[0]
    top_sector = strong_sectors[0]

    # 共振判断
    if top_leader["momentum"] > 5 and top_sector["strength"] > 3:
        confidence = 0.75
        action = "BUY"
    elif top_leader["momentum"] > 3:
        confidence = 0.60
        action = "BUY"
    else:
        confidence = 0.50
        action = "HOLD"

    # 满仓不加
    if portfolio_exposure >= 0.6 and action == "BUY":
        action = "HOLD"

    return {
        "action": action,
        "stock_code": top_leader["code"] if action == "BUY" else "",
        "stock_name": top_leader.get("name", ""),
        "momentum": top_leader.get("momentum", 0),
        "confidence": round(confidence, 2),
        "sector": top_sector.get("name", ""),
        "reason": f"{top_sector['name']} {top_sector['strength']:.1f} + {top_leader['name']} {top_leader['momentum']}%",
    }
