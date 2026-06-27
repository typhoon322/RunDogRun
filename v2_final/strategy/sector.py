"""
v2_final/strategy/sector.py — 板块强度
========================================
极简: 涨跌幅排序 → 前3强板块
"""
from typing import Any


def calc_sector_strength(sectors: list[dict]) -> list[dict[str, Any]]:
    """计算板块强度 (涨幅排序)"""
    result = []
    for s in sectors:
        chg = s.get("change_pct", 0)
        up = s.get("up_count", 0)
        down = s.get("down_count", 0)
        total = up + down if up + down > 0 else 1

        result.append({
            "name": s["name"],
            "change_pct": round(chg, 2),
            "strength": round(chg + (up / total) * 3, 1),  # 涨跌 + 宽度加成
            "up_ratio": round(up / total, 2),
            "leader": s.get("leader", ""),
        })

    ranked = sorted(result, key=lambda x: x["strength"], reverse=True)
    # 标注级别
    for i, r in enumerate(ranked):
        if r["strength"] > 5:
            r["level"] = "strong"
        elif r["strength"] > 2:
            r["level"] = "moderate"
        else:
            r["level"] = "weak"

    return ranked


def top_sectors(sector_rank: list[dict], n: int = 3) -> list[dict]:
    """返回前N强板块"""
    return [s for s in sector_rank if s["level"] == "strong"][:n]
