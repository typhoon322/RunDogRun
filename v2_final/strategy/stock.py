"""
v2_final/strategy/stock.py — 极简选股
=========================================
条件: 涨>3% + 量>1百万 + 非ST + PE>0
"""
from typing import Any


def pick_leaders(stocks: list[dict], top_n: int = 10) -> list[dict[str, Any]]:
    """极简龙头筛选"""
    candidates = []
    for s in stocks:
        code = s.get("code", "")
        name = s.get("name", "")
        chg = s.get("change_pct", 0)
        vol = s.get("volume", 0)
        pe = s.get("pe", 0)

        # 过滤: ST / 次新股 / 亏损 / 无成交
        if "ST" in name or "N" in name or "*" in name:
            continue
        if code.startswith(("8", "9")):
            continue  # 北交所跳过
        if pe <= 0:
            continue

        # 龙头条件
        if chg > 3 and vol > 1e6:
            candidates.append({
                "code": code, "name": name,
                "momentum": round(chg, 2),
                "volume": int(vol),
                "amount_yi": round(s.get("amount", 0) / 1e8, 2),
                "pe": round(pe, 1),
            })

    return sorted(candidates, key=lambda x: x["momentum"], reverse=True)[:top_n]
