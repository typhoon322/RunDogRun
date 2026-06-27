"""
resonance.py — v6 多周期共振评分
==================================
判断 日/周/月 三级方向是否一致
"""
import logging
from typing import Any

logger = logging.getLogger("quant.v6.resonance")


def compute_resonance(
    multi_cycle_data: dict[str, Any],
    sectors: list[dict[str, Any]],
    stocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    计算整体共振分数 + 各板块共振状态。

    Returns:
        {overall: {score, label}, sectors: {name: {score, label, alignment}}, ...}
    """
    sector_resonance = {}
    overall_scores = []

    for sec in sectors:
        name = sec.get("name", "")
        multi = multi_cycle_data.get("sectors", {}).get(name, {})

        daily = multi.get("daily", {})
        weekly = multi.get("weekly", {})
        monthly = multi.get("monthly", {})

        score, alignment = _resonance_score(
            daily.get("change_pct", 0),
            weekly.get("avg_change", 0),
            monthly.get("avg_change", 0),
        )

        sector_resonance[name] = {
            "score": score,
            "label": _score_label(score),
            "alignment": alignment,
        }
        overall_scores.append(score)

    # 整体共振 = 各板块均值
    avg_score = round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else 0.0
    strong_count = sum(1 for s in sector_resonance.values() if s["score"] >= 2)

    overall = {
        "score": avg_score,
        "label": "strong_alignment" if avg_score >= 2.5 else (
            "moderate" if avg_score >= 1.5 else (
                "weak" if avg_score >= 0.5 else "conflict"
            )
        ),
        "resonant_sectors": strong_count,
        "total_sectors": len(overall_scores),
    }

    logger.info(f"共振: {overall['label']}({avg_score}), {strong_count}板块共振")
    return {"overall": overall, "sectors": sector_resonance}


def _resonance_score(daily: float, weekly: float, monthly: float) -> tuple[int, str]:
    """
    计算共振分数 (0-3)。

    - 3个同向 → 3分 (强共振)
    - 2个同向 → 2分
    - 1个方向 → 1分
    - 方向矛盾 → 0分
    """
    def direction(v):
        if v > 0.5:
            return 1   # up
        elif v < -0.5:
            return -1  # down
        return 0       # flat

    d, w, m = direction(daily), direction(weekly), direction(monthly)
    directions = [d, w, m]
    pos = directions.count(1)
    neg = directions.count(-1)
    flat = directions.count(0)

    # 同方向
    if pos == 3 or neg == 3:
        return (3, "triple_align")
    # 两个同向
    if pos == 2 or neg == 2:
        return (2, "dual_align")
    # 一个方向
    if pos == 1 or neg == 1:
        return (1, "single_align")
    # 全部横盘或矛盾
    if pos > 0 and neg > 0:
        return (0, "conflict")
    return (0, "flat")


def _score_label(score: int) -> str:
    if score == 3:
        return "triple"
    if score == 2:
        return "dual"
    if score == 1:
        return "single"
    return "none"
