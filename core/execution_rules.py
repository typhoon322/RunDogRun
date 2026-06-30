"""
core/execution_rules.py — v3 Lite 交易执行规则层
=====================================================
这不是预测系统，是交易过滤器。
只允许在高质量条件下出手，防手滑、防追涨、防抄底。

规则来源: trend(趋势) / flow(流动性) / system_score(综合强度)
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.rules")

STATE_FILE = "state/execution_state.json"

# ── 因子阈值 ──
TREND_MIN = 65       # 趋势最低线
FLOW_MIN = 55        # 流动性最低线
SCORE_BUY = 70       # 系统强度买入线
SCORE_STRONG = 80    # 可加仓线
SCORE_CAUTION = 60   # 减仓线
SCORE_EXIT = 50      # 清仓线

# ── 禁止区阈值 ──
TREND_CRASH = 50     # 趋势崩坏
FLOW_DRY = 45        # 流动性枯竭
SCORE_OVERHEAT = 85  # 系统过热(假强)
COOLING_DAYS = 3     # 连续亏损冷却天数


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_trades": [], "cooling_until": None}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════
# ① 买入规则
# ═══════════════════════════════════════════

def can_buy(trend: float, flow: float, system_score: float) -> tuple[bool, str]:
    """
    强制买入条件:
      trend ≥ 65 AND system_score ≥ 70 AND flow ≥ 55

    Returns:
        (True, "✅ 允许买入") 或 (False, "❌ 原因")
    """
    checks = []

    if trend < TREND_MIN:
        checks.append(f"趋势不足 (trend={trend:.0f}<{TREND_MIN})")
    if system_score < SCORE_BUY:
        checks.append(f"系统强度不足 (score={system_score:.0f}<{SCORE_BUY})")
    if flow < FLOW_MIN:
        checks.append(f"流动性不足 (flow={flow:.0f}<{FLOW_MIN})")

    if checks:
        return False, "❌ " + ", ".join(checks)

    return True, "✅ 允许买入"


# ═══════════════════════════════════════════
# ② 禁止交易规则 (任一命中即禁止)
# ═══════════════════════════════════════════

def in_no_trade_zone(
    trend: float, flow: float, system_score: float,
    recent_return_5d: float = 0,
) -> tuple[bool, str]:
    """
    禁止区检测:
      A: trend < 50 (趋势崩坏)
      B: system_score > 85 AND recent_return < 0 (假强)
      C: flow < 45 (流动性枯竭)
      D: 连续3次亏损 → 冷却3天

    Returns:
        (True, "🚫 禁止原因") 或 (False, "")
    """
    reasons = []

    # Rule A: 趋势崩坏
    if trend < TREND_CRASH:
        reasons.append(f"趋势崩坏 (trend={trend:.0f}<{TREND_CRASH})")

    # Rule B: 系统过热假强
    if system_score > SCORE_OVERHEAT and recent_return_5d < 0:
        reasons.append(f"系统过热假强 (score={system_score:.0f}>{SCORE_OVERHEAT}, 5日收益<0)")

    # Rule C: 流动性枯竭
    if flow < FLOW_DRY:
        reasons.append(f"流动性枯竭 (flow={flow:.0f}<{FLOW_DRY})")

    # Rule D: 连续亏损冷却
    state = load_state()
    cooling_until = state.get("cooling_until")
    if cooling_until:
        today = datetime.now(CN_TZ).strftime("%Y-%m-%d")
        if today <= cooling_until:
            reasons.append(f"冷却中 (至 {cooling_until}, 连续亏损3次)")

    if reasons:
        return True, "🚫 " + ", ".join(reasons)

    return False, ""


# ═══════════════════════════════════════════
# ③ 仓位管理
# ═══════════════════════════════════════════

def position_action(
    system_score: float,
    position_profit: float = 0,
) -> dict:
    """
    仓位决策:
      score ≥ 80 AND 盈利 → 可加仓50%
      score < 60 → 减仓50%
      score < 50 → 清仓
      其他 → 持仓不动
    """
    if system_score < SCORE_EXIT:
        return {"action": "CLEAR", "reason": f"系统强度<{SCORE_EXIT}, 强制清仓", "change_pct": -100}
    if system_score < SCORE_CAUTION:
        return {"action": "REDUCE", "reason": f"系统强度<{SCORE_CAUTION}, 减仓50%", "change_pct": -50}
    if system_score >= SCORE_STRONG and position_profit > 0:
        return {"action": "ADD", "reason": f"系统强势+盈利, 加仓50%", "change_pct": +50}

    return {"action": "HOLD", "reason": "正常持有", "change_pct": 0}


# ═══════════════════════════════════════════
# ④ 完整决策矩阵
# ═══════════════════════════════════════════

def decide(
    system_score: float,
    trend: float,
    flow: float,
    recent_return_5d: float = 0,
    position_profit: float = 0,
) -> dict:
    """
    统一决策入口 — 每天只看这个。

    Returns:
        {
            "decision": "BUY / ADD / HOLD / OBSERVE / CLEAR / NO_TRADE",
            "emoji": "🟢 / 🟡 / 🔴 / ⚪",
            "details": [...],
            "can_buy": bool,
            "in_danger": bool,
            "position_action": {...},
        }
    """
    details = []

    # Step 1: 禁止区检查
    danger, danger_reason = in_no_trade_zone(trend, flow, system_score, recent_return_5d)
    if danger:
        details.append(danger_reason)
        return {
            "decision": "NO_TRADE",
            "emoji": "🔴",
            "details": details,
            "can_buy": False,
            "in_danger": True,
            "position_action": {"action": "CLEAR", "reason": "禁止区, 建议清仓", "change_pct": -100},
        }

    # Step 2: 买入检查
    buy_ok, buy_reason = can_buy(trend, flow, system_score)
    details.append(buy_reason)

    # Step 3: 仓位决策
    pa = position_action(system_score, position_profit)

    # Step 4: 决策矩阵
    if system_score >= SCORE_STRONG and buy_ok:
        decision, emoji = "STRONG_BUY", "🟢"
        details.append(f"强买信号: score={system_score:.0f}≥{SCORE_STRONG}")
    elif system_score >= SCORE_BUY and buy_ok:
        decision, emoji = "BUY", "🟢"
        details.append(f"买入信号: score={system_score:.0f}≥{SCORE_BUY}")
    elif system_score >= SCORE_CAUTION:
        decision, emoji = "OBSERVE", "🟡"
        details.append(f"观望: {SCORE_CAUTION}≤score<{SCORE_BUY}")
    elif system_score >= SCORE_EXIT:
        decision, emoji = "REDUCE", "🟡"
        details.append(f"减仓: {SCORE_EXIT}≤score<{SCORE_CAUTION}")
    else:
        decision, emoji = "CLEAR", "🔴"
        details.append(f"清仓: score={system_score:.0f}<{SCORE_EXIT}")

    return {
        "decision": decision,
        "emoji": emoji,
        "details": details,
        "can_buy": buy_ok,
        "in_danger": False,
        "position_action": pa,
        "thresholds": {
            "trend": {"value": trend, "min": TREND_MIN},
            "flow": {"value": flow, "min": FLOW_MIN},
            "score": {"value": system_score, "buy": SCORE_BUY, "strong": SCORE_STRONG,
                      "caution": SCORE_CAUTION, "exit": SCORE_EXIT},
        },
    }


# ═══════════════════════════════════════════
# ⑤ 反馈闭环: 记录交易结果
# ═══════════════════════════════════════════

def record_trade_result(profit: float):
    """记录最近一笔交易盈亏, 触发冷却机制"""
    state = load_state()
    trades = state.get("last_trades", [])
    trades.append({"profit": round(profit, 4), "date": datetime.now(CN_TZ).strftime("%Y-%m-%d")})
    trades = trades[-10:]  # 保留最近10笔

    # v3 FINAL: 冷却规则
    #   1次亏损 → 冷却3天
    #   连续3次亏损 → 冷却5天
    from datetime import timedelta

    if profit < 0:
        cooldown_days = COOLING_DAYS  # 3天
        # 检查是否连续3次亏损
        recent = trades[-3:]
        if len(recent) == 3 and all(t["profit"] < 0 for t in recent):
            cooldown_days = 5
        cooldown = datetime.now(CN_TZ) + timedelta(days=cooldown_days)
        state["cooling_until"] = cooldown.strftime("%Y-%m-%d")
        logger.warning(f"亏损{profit:+.2%}, 强制冷却 {cooldown_days}天 至 {state['cooling_until']}")

    state["last_trades"] = trades
    save_state(state)


# ═══════════════════════════════════════════
# ⑥ v3 FINAL: 仓位控制系统
# ═══════════════════════════════════════════

# Score → 仓位映射
SCORE_POSITION_MAP = [
    (80, 1.00),   # 80+ → 满仓
    (75, 0.60),   # 75-80 → 60%
    (70, 0.30),   # 70-75 → 30%
]

MAX_TOTAL_POSITION = 0.70      # 总仓位上限 70%
MAX_SINGLE_RISK = 0.10         # 单票风险上限 10%
RISK_COMPRESSED_MAX = 0.30     # 风险压缩下最大仓位

VIOLATION_LOG = "logs/violations.jsonl"


def calc_position_size(
    system_score: float,
    trend: float,
    flow: float,
    consecutive_losses: int = 0,
) -> dict:
    """
    计算推荐仓位。

    Returns:
        {target_pct: 0.30, reason: "score 73 → 30%", compressed: False}
    """
    # Step 1: Score → 基础仓位
    target = 0.0
    for threshold, size in SCORE_POSITION_MAP:
        if system_score >= threshold:
            target = size
            break

    if target == 0:
        return {"target_pct": 0.0, "reason": f"score={system_score:.0f}<70, 不建仓", "compressed": False}

    reason = f"score={system_score:.0f} → {target:.0%}"

    # Step 2: 风险压缩 (trend<60 或 flow<55 → max 30%)
    compressed = False
    if trend < 60 or flow < 55:
        target = min(target, RISK_COMPRESSED_MAX)
        reason += f", 风险压缩(trend={trend:.0f},flow={flow:.0f})"
        compressed = True

    # Step 3: 连亏降杠杆
    if consecutive_losses >= 2:
        target *= 0.5
        reason += f", 连亏{consecutive_losses}次×0.5"

    # Step 4: 总仓上限
    target = min(target, MAX_TOTAL_POSITION)

    return {
        "target_pct": round(target, 2),
        "reason": reason,
        "compressed": compressed,
        "single_stock_max": round(MAX_SINGLE_RISK, 2),
    }


def log_violation(violation_type: str, reason: str):
    """违例记录 — 每周必须回看"""
    import json as _json
    os.makedirs(os.path.dirname(VIOLATION_LOG), exist_ok=True)
    entry = {
        "date": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M"),
        "type": violation_type,
        "reason": reason,
        "penalty": True,
    }
    with open(VIOLATION_LOG, "a", encoding="utf-8") as f:
        f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    logger.warning(f"⚠️ 违例: {violation_type} — {reason}")


def get_cooling_status() -> dict:
    """当前冷却状态"""
    state = load_state()
    cooling = state.get("cooling_until")
    today = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    if cooling and today <= cooling:
        return {"in_cooldown": True, "until": cooling, "reason": "连续亏损冷却"}
    trades = state.get("last_trades", [])
    losses = sum(1 for t in trades[-3:] if t.get("profit", 0) < 0)
    return {
        "in_cooldown": False,
        "consecutive_losses": losses if len(trades) >= 3 else 0,
        "recent_trades": len(trades),
    }


def print_decision(result: dict):
    """控制台友好输出"""
    print()
    print("─" * 40)
    print(f"  🎯 今日决策: {result['emoji']} {result['decision']}")
    print("─" * 40)
    for d in result.get("details", []):
        print(f"  {d}")
    pa = result.get("position_action", {})
    if pa:
        print(f"  仓位: {pa.get('action', '?')} — {pa.get('reason', '')}")
    print("─" * 40)
