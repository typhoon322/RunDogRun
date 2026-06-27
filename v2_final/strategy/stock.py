"""
v2_final/strategy/stock.py — v2.1 低价优选选股
=================================================
Score = 40%动量 + 30%板块强度 + 20%成交量 + 10%低价加成
"""
from typing import Any


def pick_leaders(stocks: list[dict], sector_rank: list[dict] | None = None,
                 top_n: int = 10) -> list[dict[str, Any]]:
    """v2.1 综合评分选股"""
    # 板块强度快查
    sector_map = {}
    if sector_rank:
        sector_map = {s["name"]: s["strength"] for s in sector_rank}

    candidates = []
    for s in stocks:
        code = s.get("code", "")
        name = s.get("name", "")
        chg = s.get("change_pct", 0)
        vol = s.get("volume", 0)
        pe = s.get("pe", 0)
        price = s.get("price", 0)

        # 过滤
        if "ST" in name or "N" in name or "*" in name:
            continue
        if code.startswith(("8", "9")):
            continue
        if pe <= 0 or price <= 0 or chg < 2:
            continue
        if vol < 5e5:
            continue

        # v2.1 综合评分
        momentum_score = chg * 0.4
        sector_score = sector_map.get(name, 3) * 0.07  # 板块加成
        volume_score = min(2.0, vol / 5e6) * 0.20
        # 低价偏好: 价格越低分越高 (适合小资金分仓)
        price_score = (1 / (price + 1)) * 10 * 0.10

        score = round(momentum_score + sector_score + volume_score + price_score, 2)

        candidates.append({
            "code": code, "name": name,
            "price": round(price, 2),
            "momentum": round(chg, 2),
            "volume": int(vol),
            "amount_yi": round(s.get("amount", 0) / 1e8, 2),
            "pe": round(pe, 1),
            "score": score,
            "breakdown": {
                "momentum_weight": round(momentum_score, 2),
                "sector_weight": round(sector_score, 2),
                "volume_weight": round(volume_score, 2),
                "price_weight": round(price_score, 2),
            },
        })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:top_n]
