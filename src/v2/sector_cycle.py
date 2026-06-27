"""
cycle_engine.py — v2 板块轮动周期模型
========================================
7阶段周期判定 + 市场总周期 + v1控制调度

核心: 资金在不同板块间周期性轮动
阶段: Dormant→Start→Confirm→Expansion→Climax→Divergence→Decline
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("quant-collector.cycle")


# ============================================================
# 阶段定义
# ============================================================

STAGE_DORMANT = "dormant"          # 沉寂期: 无资金关注
STAGE_START = "start"              # 启动期: 资金试探
STAGE_CONFIRM = "confirm"          # 确认期: 主线确认
STAGE_EXPANSION = "expansion"      # 发酵期: 最赚钱阶段 ⭐
STAGE_CLIMAX = "climax"            # 高潮期: 风险上升
STAGE_DIVERGENCE = "divergence"    # 分化期: 资金撤退
STAGE_DECLINE = "decline"          # 退潮期: 完全退出

STAGE_ORDER = [
    STAGE_DORMANT, STAGE_START, STAGE_CONFIRM,
    STAGE_EXPANSION, STAGE_CLIMAX, STAGE_DIVERGENCE, STAGE_DECLINE,
]

STAGE_LABELS = {
    STAGE_DORMANT:     "沉寂期",
    STAGE_START:       "启动期",
    STAGE_CONFIRM:     "确认期",
    STAGE_EXPANSION:   "发酵期",
    STAGE_CLIMAX:      "高潮期",
    STAGE_DIVERGENCE:  "分化期",
    STAGE_DECLINE:     "退潮期",
}

# 周期分值 → 阶段映射
# high cycle_score = 早期阶段（启动/发酵）→ 买入机会
# low cycle_score = 后期阶段（高潮/退潮）→ 风险
def _score_to_stage(score: int) -> str:
    if score >= 8:
        return STAGE_EXPANSION
    elif score == 7:
        return STAGE_CONFIRM
    elif score == 6:
        return STAGE_START
    elif score == 5:
        return STAGE_CLIMAX
    elif 3 <= score <= 4:
        return STAGE_DIVERGENCE
    else:
        return STAGE_DECLINE


# ============================================================
# 历史加载
# ============================================================

def _load_history(
    data_dir: str,
    target_date: str,
    lookback: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    """加载板块多日历史数据"""
    hist: dict[str, list] = defaultdict(list)
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    for offset in range(lookback, 0, -1):
        check_dt = target_dt - timedelta(days=offset)
        check_date = check_dt.strftime("%Y-%m-%d")
        filepath = Path(data_dir) / f"{check_date}.json"
        if not filepath.exists():
            continue
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("data_quality") == "failed":
            continue
        for sector in data.get("sectors", []):
            name = sector.get("name", "")
            hist[name].append(sector)
    return dict(hist)


# ============================================================
# 四大核心指标
# ============================================================

def _score_momentum(
    today: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[int, str]:
    """
    Momentum (0-4): 3日 vs 10日加速度
    加速上升 → 高分 (启动/确认特征)
    减速 → 低分 (分化/退潮)
    """
    if len(history) >= 10:
        recent_3 = [h.get("change_pct", 0) for h in history[-3:]]
        recent_10 = [h.get("change_pct", 0) for h in history[-10:]]
        avg_3 = sum(recent_3) / 3
        avg_10 = sum(recent_10) / 10
        accel = avg_3 - avg_10

        if accel > 1.5:
            return (4, "strong_accel")
        elif accel > 0.5:
            return (3, "accelerating")
        elif accel > 0:
            return (2, "slight_up")
        elif accel > -0.5:
            return (1, "flattening")
        else:
            return (0, "decelerating")
    elif len(history) >= 3:
        recent_3 = [h.get("change_pct", 0) for h in history[-3:]]
        avg_3 = sum(recent_3) / 3
        if avg_3 > 1:
            return (2, "recent_up")
        elif avg_3 > 0:
            return (1, "recent_flat")
        else:
            return (0, "recent_down")
    else:
        chg = today.get("change_pct", 0)
        return (2 if chg > 2 else (1 if chg > 0 else 0), "single_day")


def _score_breadth(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[int, str]:
    """
    Breadth (0-3) ⭐最重要
    - 当前上涨占比
    - 上涨占比变化趋势
    - 涨停家数变化
    """
    total = sector.get("total_stocks", 0)
    up = sector.get("up_count", 0)
    if total <= 0:
        return (1, "no_data")

    cur_ratio = up / total

    # 当前宽度
    if cur_ratio >= 0.70:
        base = 3
    elif cur_ratio >= 0.40:
        base = 2
    elif cur_ratio >= 0.20:
        base = 1
    else:
        base = 0

    # 历史趋势调整
    if len(history) >= 3:
        prev_ratios = []
        for h in history[-3:]:
            t = h.get("total_stocks", 0)
            u = h.get("up_count", 0)
            prev_ratios.append(u / t if t > 0 else 0)
        prev_avg = sum(prev_ratios) / len(prev_ratios)

        if cur_ratio > prev_avg + 0.10:  # Breadth 明显扩大
            base = min(3, base + 1)
        elif cur_ratio < prev_avg - 0.10:  # Breadth 收缩
            base = max(0, base - 1)

    label = "wide" if base == 3 else ("medium" if base == 2 else ("narrow" if base == 1 else "thin"))
    return (base, label)


def _score_volume_flow(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> tuple[int, str]:
    """
    Volume Flow (0-3): 资金流持续性
    - 当前资金流向
    - 成交量趋势
    """
    mf = sector.get("money_flow", "neutral")
    # 资金流向映射
    flow_map = {"strong_inflow": 3, "positive": 2, "neutral": 1, "negative": 0,
                 "strong_outflow": 0}
    base = flow_map.get(mf, 1)

    # 持续性: 连续N天正向
    if len(history) >= 3:
        recent_flows = [h.get("money_flow", "neutral") for h in history[-3:]]
        pos_days = sum(1 for f in recent_flows if f in ("strong_inflow", "positive"))
        if pos_days >= 2 and mf in ("strong_inflow", "positive"):
            base = min(3, base + 1)
        elif pos_days == 0 and mf in ("negative", "strong_outflow"):
            base = max(0, base - 1)

    label = "strong" if base >= 3 else ("moderate" if base == 2 else ("weak" if base == 1 else "outflow"))
    return (base, label)


def _score_leadership(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> int:
    """
    Leadership (0-3): 龙头强度
    - 领涨股涨跌幅 vs 板块涨跌幅
    - 龙头持续性
    """
    leader_pct = sector.get("leader_change_pct", 0)
    sector_pct = sector.get("change_pct", 0)
    leader_name = sector.get("leader_name", "")
    leader_code = sector.get("leader_code", "")

    # 无龙头数据
    if not leader_name or leader_pct == 0:
        return 1

    # 龙头能否跑赢板块
    leader_alpha = leader_pct - sector_pct
    if leader_alpha > 3:
        base = 3
    elif leader_alpha > 1:
        base = 2
    elif leader_alpha >= 0:
        base = 1
    else:
        base = 0

    # 龙头持续性: 是否连续领涨
    if len(history) >= 3 and leader_code:
        same_leader_count = sum(
            1 for h in history[-3:]
            if h.get("leader_code") == leader_code
        )
        if same_leader_count >= 2:
            base = min(3, base + 1)

    return base


# ============================================================
# 周期判定
# ============================================================

def classify_cycle(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    判定单个板块的周期阶段。

    Returns:
        {cycle_stage, cycle_score, cycle_label,
         momentum_score, breadth_score, volume_score, leadership_score,
         priority, v1_advice}
    """
    name = sector.get("name", "?")

    # 沉寂期快速判断
    if _is_dormant(sector, history):
        return {
            "name": name, "code": sector.get("code", ""),
            "cycle_stage": STAGE_DORMANT, "cycle_score": 0,
            "cycle_label": STAGE_LABELS[STAGE_DORMANT],
            "momentum_score": 0, "momentum_label": "none",
            "breadth_score": 0, "breadth_label": "thin",
            "volume_score": 0, "volume_label": "none",
            "leadership_score": 0,
            "change_pct": sector.get("change_pct", 0),
            "priority": 0, "v1_advice": "skip",
        }

    # 四大指标
    m_score, m_label = _score_momentum(sector, history)
    b_score, b_label = _score_breadth(sector, history)
    v_score, v_label = _score_volume_flow(sector, history)
    l_score = _score_leadership(sector, history)

    # 总分 (0-14) → 映射到周期
    raw_total = m_score + (b_score * 2) + v_score + l_score  # Breadth 权重 x2
    # 归一化到 0-10
    cycle_score = min(10, max(0, int(raw_total * 10 / 14 + 0.5)))

    cycle_stage = _score_to_stage(cycle_score)

    # v1 控制建议
    v1_advice = _get_v1_advice(cycle_stage, cycle_score)

    return {
        "name": name,
        "code": sector.get("code", ""),
        "cycle_stage": cycle_stage,
        "cycle_score": cycle_score,
        "cycle_label": STAGE_LABELS.get(cycle_stage, "未知"),
        "momentum_score": m_score,
        "momentum_label": m_label,
        "breadth_score": b_score,
        "breadth_label": b_label,
        "volume_score": v_score,
        "volume_label": v_label,
        "leadership_score": l_score,
        "change_pct": sector.get("change_pct", 0),
        "priority": 0,
        "v1_advice": v1_advice,
    }


def _is_dormant(
    sector: dict[str, Any],
    history: list[dict[str, Any]],
) -> bool:
    """沉寂期判定: 无涨跌 + 无量 + 无关注"""
    chg = abs(sector.get("change_pct", 0))
    up = sector.get("up_count", 0)
    total = sector.get("total_stocks", 1)
    ratio = up / total if total > 0 else 0

    # 长期低活跃
    if len(history) >= 10:
        recent_chgs = [abs(h.get("change_pct", 0)) for h in history[-10:]]
        avg_chg = sum(recent_chgs) / len(recent_chgs)
        if avg_chg < 0.3 and ratio < 0.15 and chg < 0.5:
            return True

    # 短期沉寂: 当日变化<0.3% + 上涨<15%
    if chg < 0.3 and ratio < 0.15 and len(history) < 3:
        return True

    return False


def _get_v1_advice(stage: str, score: int) -> str:
    """根据周期阶段给出 v1 系统控制建议"""
    advice = {
        STAGE_DORMANT:     "skip: 无资金, 禁止交易",
        STAGE_START:       "monitor: 观察龙头异动, 轻仓试探",
        STAGE_CONFIRM:     "engage: 确认方向, 可加仓",
        STAGE_EXPANSION:   "full: 黄金期, 全力做多, 权重×1.2",
        STAGE_CLIMAX:      "caution: 只允许A+信号, 降仓",
        STAGE_DIVERGENCE:  "reduce: 只卖出, 不允许新开仓",
        STAGE_DECLINE:     "exit: 禁止交易, 清仓",
    }
    return advice.get(stage, "unknown")


# ============================================================
# 市场总周期
# ============================================================

def classify_market_cycle(
    sector_cycles: list[dict[str, Any]],
    sentiment: dict[str, Any] | None = None,
    market_status: str = "neutral",
) -> dict[str, Any]:
    """
    市场整体周期判定。

    Risk-On:  多板块处于 Expansion/Confirm, 涨停多, 指数上行
    Neutral:  混合状态
    Risk-Off: 多板块处于 Decline/Divergence, 跌停多
    """
    if not sector_cycles:
        return {"market_state": "risk_off", "market_cycle": "decline", "confidence": 0.3}

    # 统计各阶段板块数
    stage_counts = defaultdict(int)
    for sc in sector_cycles:
        stage_counts[sc["cycle_stage"]] += 1
    total = len(sector_cycles)

    expansion_pct = (stage_counts[STAGE_EXPANSION] + stage_counts[STAGE_CONFIRM]) / total
    decline_pct = (stage_counts[STAGE_DECLINE] + stage_counts[STAGE_DIVERGENCE]) / total

    # 情绪辅助
    risk_level = sentiment.get("risk_level", "medium") if sentiment else "medium"
    limit_up = sentiment.get("limit_up_count", 0) if sentiment else 0
    limit_down = sentiment.get("limit_down_count", 0) if sentiment else 0

    if expansion_pct >= 0.25 and decline_pct < 0.30 and limit_up > limit_down * 2:
        market_state = "risk_on"
        market_cycle = "expansion"
        confidence = 0.75 if expansion_pct >= 0.35 else 0.60
    elif decline_pct >= 0.30 or (limit_down > 50 and limit_up < 30):
        market_state = "risk_off"
        market_cycle = "decline" if decline_pct >= 0.40 else "divergence"
        confidence = 0.75 if decline_pct >= 0.50 else 0.60
    else:
        market_state = "neutral"
        # 判断偏多还是偏空
        if expansion_pct > decline_pct:
            market_cycle = "start"
        elif decline_pct > expansion_pct:
            market_cycle = "divergence"
        else:
            market_cycle = "neutral"
        confidence = 0.50

    return {
        "market_state": market_state,
        "market_cycle": market_cycle,
        "confidence": confidence,
        "stage_distribution": dict(stage_counts),
        "expansion_ratio": round(expansion_pct, 2),
        "decline_ratio": round(decline_pct, 2),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
    }


# ============================================================
# 主入口
# ============================================================

def analyze_cycle(
    date_str: str,
    data_dir: str = config.DATA_DIR,
) -> dict[str, Any]:
    """
    v2 完整周期分析。

    Args:
        date_str: 分析日期
        data_dir: 数据目录

    Returns:
        周期分析报告
    """
    # 1. 读取当日数据
    data_path = Path(data_dir) / f"{date_str}.json"
    if not data_path.exists():
        logger.error(f"数据不存在: {data_path}")
        return {"date": date_str, "error": "data_not_found", "version": "2.0.0"}

    with open(data_path, encoding="utf-8") as f:
        today_data = json.load(f)

    sectors_today = today_data.get("sectors", [])
    sentiment = today_data.get("sentiment", {})
    market_status = today_data.get("market", {}).get("market_status", "neutral")

    if not sectors_today:
        return {"date": date_str, "error": "empty_sectors", "version": "2.0.0"}

    # 2. 加载历史
    history = _load_history(data_dir, date_str)
    logger.info(f"周期分析: {len(sectors_today)} 板块, {len(history)} 有历史")

    # 3. 对每个板块判定周期
    sector_cycles = []
    for sector in sectors_today:
        name = sector.get("name", "")
        hist = history.get(name, [])
        cycle = classify_cycle(sector, hist)
        sector_cycles.append(cycle)

    # 4. 按周期阶段排序 (expansion > confirm > start > climax > divergence > decline > dormant)
    stage_rank = {
        STAGE_EXPANSION: 7, STAGE_CONFIRM: 6, STAGE_START: 5,
        STAGE_CLIMAX: 4, STAGE_DIVERGENCE: 3, STAGE_DECLINE: 2, STAGE_DORMANT: 1,
    }
    sector_cycles.sort(key=lambda x: stage_rank.get(x["cycle_stage"], 0), reverse=True)

    # 优先级标注
    for i, sc in enumerate(sector_cycles):
        sc["priority"] = i + 1

    # 5. 市场总周期
    market_cycle = classify_market_cycle(sector_cycles, sentiment, market_status)

    # 6. 交易偏好
    trade_bias = {
        "preferred_stage": [STAGE_CONFIRM, STAGE_EXPANSION],
        "neutral_stage": [STAGE_START, STAGE_CLIMAX],
        "avoid_stage": [STAGE_DIVERGENCE, STAGE_DECLINE, STAGE_DORMANT],
    }

    # 7. 过滤出可交易板块 (前15个非退潮/沉寂板块)
    tradable = [
        sc for sc in sector_cycles
        if sc["cycle_stage"] not in (STAGE_DECLINE, STAGE_DORMANT, STAGE_DIVERGENCE)
    ][:15]

    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "2.0.0",
        "market_state": market_cycle["market_state"],
        "market_cycle": market_cycle["market_cycle"],
        "market_confidence": market_cycle["confidence"],
        "sector_cycles": sector_cycles,
        "tradable_sectors": tradable,
        "trade_bias": trade_bias,
        "snapshot": {
            "total_sectors": len(sector_cycles),
            "expansion_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_EXPANSION),
            "confirm_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_CONFIRM),
            "start_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_START),
            "climax_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_CLIMAX),
            "divergence_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_DIVERGENCE),
            "decline_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_DECLINE),
            "dormant_count": sum(1 for s in sector_cycles if s["cycle_stage"] == STAGE_DORMANT),
        },
    }

    logger.info(
        f"周期分析: 市场{market_cycle['market_state']}, "
        f"可交易{len(tradable)}板块, "
        f"Expansion={result['snapshot']['expansion_count']}"
    )
    return result
