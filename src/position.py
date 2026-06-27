"""
position.py — v1.4 仓位分配 + 风险控制
========================================
信号→仓位映射、组合限制、止损规则、极端风险降仓
"""

import logging
from typing import Any

import config

logger = logging.getLogger("quant-collector.position")


def allocate_position(
    signal: dict[str, Any],
    sector_exposure: float = 0.0,
    current_positions: int = 0,
) -> float:
    """
    根据信号等级分配仓位。

    Args:
        signal: 信号字典 {signal_grade, confidence}
        sector_exposure: 当前板块已占用仓位比例
        current_positions: 当前持仓数

    Returns:
        建议仓位比例 (0.0 ~ 0.30)
    """
    grade = signal.get("signal_grade", "B")

    # 基础仓位
    if grade == "A+":
        base = max(config.POSITION_A_PLUS)
    elif grade == "A":
        base = sum(config.POSITION_A) / 2  # 20%
    elif grade == "B":
        base = config.POSITION_B[0]  # 5%
    elif grade == "C":
        base = config.POSITION_C  # 5%
    else:
        base = 0.05

    # 置信度调整
    confidence = signal.get("confidence", 0.5)
    adjusted = base * (0.5 + confidence)

    # 板块集中度限制
    remain = config.POSITION_MAX_SECTOR_EXPOSURE - sector_exposure
    if remain <= 0:
        logger.warning("板块集中度已达上限, 跳过")
        return 0.0
    adjusted = min(adjusted, remain)

    # 持仓数量限制
    if current_positions >= config.POSITION_MAX_COUNT:
        logger.warning(f"持仓数已达上限 {config.POSITION_MAX_COUNT}")
        return 0.0

    # 单票上限
    adjusted = min(adjusted, config.POSITION_MAX_SINGLE)

    # 下限保护
    adjusted = max(adjusted, 0.03)

    return round(adjusted, 2)


def compute_stop_loss(
    signal_grade: str,
    stock: dict[str, Any],
) -> str:
    """
    计算止损线。

    A+→-8%, A→-10%, B/C→-12%
    """
    if signal_grade == "A+":
        pct = config.STOP_LOSS_PCT_AGGRESSIVE
    elif signal_grade == "A":
        pct = config.STOP_LOSS_PCT
    else:
        pct = config.STOP_LOSS_PCT_WIDE

    return f"{pct:.0%}"


def compute_portfolio_risk(
    positions: list[dict[str, Any]],
    sentiment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    计算组合风险指标。

    Returns:
        {total_exposure, max_sector_exposure, position_count,
         risk_state, warnings}
    """
    total = sum(p.get("position_size", 0) for p in positions)
    count = len(positions)

    # 板块集中度
    from collections import defaultdict
    sector_exp = defaultdict(float)
    for p in positions:
        sec = p.get("sector", "")
        sector_exp[sec] += p.get("position_size", 0)
    max_sector = max(sector_exp.values()) if sector_exp else 0.0

    warnings = []
    risk_state = "controlled"

    if total > 0.80:
        warnings.append(f"总仓位过高: {total:.0%}")
        risk_state = "overexposed"
    if max_sector > config.POSITION_MAX_SECTOR_EXPOSURE:
        warnings.append(f"板块集中度过高: {max_sector:.0%}")
    if count > config.POSITION_MAX_COUNT:
        warnings.append(f"持仓过多: {count}>{config.POSITION_MAX_COUNT}")

    # 极端风险: 情绪high + 高仓位
    if sentiment and sentiment.get("risk_level") == config.RISK_EXTREME_SENTIMENT:
        if total > config.RISK_EXTREME_MAX_EXPOSURE:
            warnings.append(
                f"极端风险: 总仓位{total:.0%}超过{config.RISK_EXTREME_MAX_EXPOSURE:.0%}上限"
            )
            risk_state = "extreme_risk"

    return {
        "total_exposure": round(total, 2),
        "max_sector_exposure": round(max_sector, 2),
        "position_count": count,
        "risk_state": risk_state,
        "warnings": warnings,
    }
