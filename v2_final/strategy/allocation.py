"""
v2_final/strategy/allocation.py — v2.3 分仓权重
===================================================
评分加权 + 单票上限 + 最低分散度
"""
import logging
from typing import Any

logger = logging.getLogger("v2.allocation")


def allocate_portfolio(
    ranked_stocks: list[dict],
    top_n: int = 5,
    max_single: float = 0.35,
    min_single: float = 0.05,
) -> list[dict[str, Any]]:
    """
    评分加权分仓。

    Args:
        ranked_stocks: 已排序的股票列表
        top_n: 选取前N只
        max_single: 单票最大权重
        min_single: 忽略权重低于此值的

    Returns:
        [{code, name, price, score, weight, reason}, ...]
    """
    selected = ranked_stocks[:top_n]

    if not selected:
        return []

    total = sum(s["score"] for s in selected)
    if total <= 0:
        return []

    portfolio = []
    for s in selected:
        raw_weight = s["score"] / total
        # 单票上限
        weight = min(raw_weight, max_single)
        if weight < min_single:
            continue
        portfolio.append({
            "code": s["code"],
            "name": s["name"],
            "price": s["price"],
            "score": s["score"],
            "weight": round(weight, 3),
        })

    # 重新归一化
    new_total = sum(p["weight"] for p in portfolio)
    if new_total > 0 and abs(new_total - 1.0) > 0.01:
        for p in portfolio:
            p["weight"] = round(p["weight"] / new_total, 3)

    logger.info(f"组合: {len(portfolio)} 只 "
                f"(Top: {portfolio[0]['name']} {portfolio[0]['weight']:.0%})")
    return portfolio
