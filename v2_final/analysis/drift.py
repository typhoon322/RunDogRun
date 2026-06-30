"""
v2_final/analysis/drift.py — 策略漂移检测
=============================================
对比历史 vs 近期表现, 量化策略退化程度
"""
import logging
import os
from typing import Any

logger = logging.getLogger("v2.drift")


def detect_drift(
    old_stats: dict[str, Any] | None,
    recent_stats: dict[str, Any],
) -> dict[str, Any]:
    """
    检测策略性能漂移。

    Args:
        old_stats: 历史基准 (eg. 全部回测)
        recent_stats: 近期表现 (eg. 最近20日)

    Returns:
        {drift_score, status, details}
    """
    if old_stats is None:
        return {"drift_score": 0, "status": "BASELINE", "details": ["首次运行, 无历史对比"]}

    score = 0
    details = []

    # 1. 胜率退化
    old_wr = old_stats.get("win_rate", 0)
    new_wr = recent_stats.get("win_rate", 0)
    if new_wr < old_wr - 0.05:
        score += 40
        details.append(f"胜率退化: {old_wr:.0%}→{new_wr:.0%} (Δ{new_wr-old_wr:+.0%})")

    # 2. 回撤扩大
    old_dd = abs(old_stats.get("max_drawdown_pct", 0))
    new_dd = abs(recent_stats.get("max_drawdown_pct", 0))
    if new_dd > old_dd + 3:
        score += 30
        details.append(f"回撤扩大: {old_dd:.1f}%→{new_dd:.1f}%")

    # 3. 波动加剧 (>1.3x)
    old_vol = old_stats.get("volatility", 0.02)
    new_vol = recent_stats.get("volatility", 0.02)
    if old_vol > 0 and new_vol > old_vol * 1.3:
        score += 30
        details.append(f"波动加剧: {old_vol:.2%}→{new_vol:.2%}")

    score = min(100, score)

    # 状态
    if score >= 70:
        status = "DEGRADED 🔴"
    elif score >= 40:
        status = "WARNING ⚠️"
    elif score > 0:
        status = "SLIGHT_SHIFT ⚡"
    else:
        status = "STABLE ✅"

    logger.info(f"漂移: {score}/100 {status}")
    return {"drift_score": score, "status": status, "details": details}


def compare_snapshot(old_date: str, new_date: str) -> dict[str, Any]:
    """比较两个快照是否一致 (简单文件对比)"""
    import os
    old_path = f"data/snapshots/{old_date}"
    new_path = f"data/snapshots/{new_date}"

    if not os.path.exists(old_path) or not os.path.exists(new_path):
        return {"consistent": False, "reason": "snapshot missing"}

    old_files = set(os.listdir(old_path))
    new_files = set(os.listdir(new_path))
    common = old_files & new_files

    return {
        "consistent": len(common) > 0,
        "old_count": len(old_files),
        "new_count": len(new_files),
        "common": len(common),
    }
