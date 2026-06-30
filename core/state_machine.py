"""
core/state_machine.py — V3 FINAL 生命周期状态机
=================================================
COLLECT_ONLY → WARM_UP → ACTIVE → (MONITORING) → 降级回 WARM_UP

这是系统的"大脑"——决定当前允许做什么、不允许做什么。
所有 Pipeline 行为由当前 STATE 决定, 不允许绕过。

States:
  COLLECT_ONLY  — 只收数据, 不计算 score, 不生成 signal
  WARM_UP       — 计算 score, 生成 signal (不交易), 记录 IC
  ACTIVE        — 完整交易: 决策引擎 + 仓位 + 执行
  MONITORING    — ACTIVE 的子状态, 每7天检查是否需要降级

Transitions:
  COLLECT_ONLY → WARM_UP:  days >= 10
  WARM_UP → ACTIVE:        score_stable AND signal_count >= 50 AND ic >= 0
  ACTIVE → WARM_UP:        ic < 0 OR win_rate_collapse (降级)
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger("v3.state_machine")

CN_TZ = timezone(timedelta(hours=8))

STATE_FILE = "state/lifecycle.json"

# ── 状态常量 ──
COLLECT_ONLY = "COLLECT_ONLY"
WARM_UP = "WARM_UP"
ACTIVE = "ACTIVE"
MONITORING = "MONITORING"

ALL_STATES = [COLLECT_ONLY, WARM_UP, ACTIVE, MONITORING]

# ── 状态行为定义 ──
STATE_BEHAVIOR = {
    COLLECT_ONLY: {
        "collect_data": True,
        "compute_score": False,
        "generate_signal": False,
        "run_decision": False,
        "execute_trade": False,
        "monitor": False,
    },
    WARM_UP: {
        "collect_data": True,
        "compute_score": True,
        "generate_signal": True,
        "run_decision": False,
        "execute_trade": False,
        "monitor": False,
    },
    ACTIVE: {
        "collect_data": True,
        "compute_score": True,
        "generate_signal": True,
        "run_decision": True,
        "execute_trade": True,
        "monitor": True,
    },
    MONITORING: {
        "collect_data": True,
        "compute_score": True,
        "generate_signal": True,
        "run_decision": True,
        "execute_trade": True,
        "monitor": True,
    },
}

STATE_EMOJI = {
    COLLECT_ONLY: "❄️",
    WARM_UP: "🔥",
    ACTIVE: "🚀",
    MONITORING: "🧠",
}

STATE_LABELS = {
    COLLECT_ONLY: "PHASE 1: COLD START (数据收集)",
    WARM_UP: "PHASE 2: WARM-UP (统计预热, 不交易)",
    ACTIVE: "PHASE 3: ACTIVE (实盘执行)",
    MONITORING: "PHASE 4: MONITORING (防失效检查)",
}


def _load_params() -> dict:
    """从 config/params.yaml 加载参数"""
    import yaml
    path = Path("config/params.yaml")
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    # fallback defaults
    return {
        "state_machine": {
            "collect_only_min_days": 10,
            "warmup_exit_signal_count": 50,
            "warmup_exit_ic_min": 0.0,
            "warmup_exit_mean_drift_max": 0.05,
            "warmup_exit_std_drift_max": 0.10,
            "degrade_ic_threshold": 0.0,
            "degrade_winrate_drop": 0.15,
            "degrade_score_drift": 0.10,
            "monitor_check_interval_days": 7,
        }
    }


def load_state() -> dict:
    """加载持久化状态"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 初始状态
    return {
        "state": COLLECT_ONLY,
        "entered_at": datetime.now(CN_TZ).isoformat(),
        "history": [],
        "last_monitor_check": None,
        "monitor_checks": 0,
        "degradation_count": 0,
    }


def save_state(state: dict):
    """持久化状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    logger.info(f"状态已保存: {state['state']}")


def get_current_state() -> str:
    """获取当前状态 (不触发转换)"""
    return load_state().get("state", COLLECT_ONLY)


def get_behavior(state: str | None = None) -> dict:
    """获取当前状态允许的行为"""
    s = state or get_current_state()
    return STATE_BEHAVIOR.get(s, STATE_BEHAVIOR[COLLECT_ONLY])


def _record_transition(state_obj: dict, new_state: str, reason: str):
    """记录状态转换历史"""
    old_state = state_obj["state"]
    if old_state == new_state:
        return
    state_obj.setdefault("history", []).append({
        "from": old_state,
        "to": new_state,
        "reason": reason,
        "timestamp": datetime.now(CN_TZ).isoformat(),
    })
    state_obj["state"] = new_state
    state_obj["entered_at"] = datetime.now(CN_TZ).isoformat()
    logger.info(f"状态转换: {old_state} → {new_state} ({reason})")


def compute_stats(
    min_days: int = 0,
    signal_count: int = 0,
    ic_5d: float | None = None,
    score_history: list[float] | None = None,
    win_rate_current: float | None = None,
    win_rate_prev: float | None = None,
) -> dict:
    """
    计算状态机需要的统计指标。

    Args:
        min_days: 当前最小数据天数
        signal_count: 累积信号总数
        ic_5d: 5日 IC 值
        score_history: 近期 score 序列 (用于稳定性计算)
        win_rate_current: 当前胜率
        win_rate_prev: 上一期胜率

    Returns:
        统计指标 dict
    """
    stats = {
        "min_days": min_days,
        "signal_count": signal_count,
        "ic": ic_5d,
        "score_stable": False,
        "mean_drift": None,
        "std_drift": None,
        "win_rate_current": win_rate_current,
        "win_rate_prev": win_rate_prev,
        "win_rate_drop": None,
        "performance_drop": False,
    }

    # Score 稳定性: 需要至少 20 天数据 (10天当前 + 10天对比)
    if score_history and len(score_history) >= 20:
        try:
            import numpy as np
            recent_10 = score_history[-10:]
            prev_10 = score_history[-20:-10]
            mean_recent = float(np.mean(recent_10))
            mean_prev = float(np.mean(prev_10))
            std_recent = float(np.std(recent_10))
            std_prev = float(np.std(prev_10))

            # 漂移率 (相对于前一期)
            mean_drift = abs(mean_recent - mean_prev) / max(abs(mean_prev), 0.01) if mean_prev != 0 else 0
            std_drift = abs(std_recent - std_prev) / max(std_prev, 0.01) if std_prev != 0 else 0

            params = _load_params().get("state_machine", {})
            mean_max = params.get("warmup_exit_mean_drift_max", 0.05)
            std_max = params.get("warmup_exit_std_drift_max", 0.10)

            stats["mean_drift"] = round(mean_drift, 4)
            stats["std_drift"] = round(std_drift, 4)
            stats["score_stable"] = mean_drift < mean_max and std_drift < std_max
        except Exception as e:
            logger.warning(f"稳定性计算失败: {e}")

    # 胜率突降
    if win_rate_current is not None and win_rate_prev is not None:
        stats["win_rate_drop"] = round(win_rate_prev - win_rate_current, 4)
        params = _load_params().get("state_machine", {})
        drop_threshold = params.get("degrade_winrate_drop", 0.15)
        stats["performance_drop"] = stats["win_rate_drop"] > drop_threshold

    return stats


def update_state(stats: dict) -> dict:
    """
    核心状态机: 根据当前统计指标决定是否转换状态。

    Args:
        stats: compute_stats() 的返回值

    Returns:
        更新后的状态对象 (已持久化)
    """
    params = _load_params().get("state_machine", {})
    state_obj = load_state()
    current = state_obj["state"]
    new_state = current
    reason = ""

    if current == COLLECT_ONLY:
        min_days_threshold = params.get("collect_only_min_days", 10)
        if stats.get("min_days", 0) >= min_days_threshold:
            new_state = WARM_UP
            reason = f"数据天数 {stats['min_days']} >= {min_days_threshold}"

    elif current == WARM_UP:
        signal_min = params.get("warmup_exit_signal_count", 50)
        ic_min = params.get("warmup_exit_ic_min", 0.0)

        conditions = {
            "score_stable": stats.get("score_stable", False),
            "signal_count_ok": stats.get("signal_count", 0) >= signal_min,
            "ic_ok": stats.get("ic") is not None and stats.get("ic") >= ic_min,
        }

        if all(conditions.values()):
            new_state = ACTIVE
            reason = (
                f"score稳定({stats.get('score_stable')}) "
                f"信号数{stats.get('signal_count', 0)}>={signal_min} "
                f"IC={stats.get('ic')}>=0"
            )
        else:
            # 记录未满足的条件
            failed = [k for k, v in conditions.items() if not v]
            logger.info(f"WARM_UP 未满足条件: {failed}")

    elif current in (ACTIVE, MONITORING):
        ic_threshold = params.get("degrade_ic_threshold", 0.0)
        ic_val = stats.get("ic")
        perf_drop = stats.get("performance_drop", False)

        if (ic_val is not None and ic_val < ic_threshold) or perf_drop:
            new_state = WARM_UP
            state_obj["degradation_count"] = state_obj.get("degradation_count", 0) + 1
            if ic_val is not None and ic_val < ic_threshold:
                reason = f"IC={ic_val}<{ic_threshold} 触发降级"
            else:
                reason = f"胜率突降 {stats.get('win_rate_drop', 0):.0%} 触发降级"
            logger.warning(f"⚠️ 系统降级: {current} → WARM_UP ({reason})")

    _record_transition(state_obj, new_state, reason)
    save_state(state_obj)
    return state_obj


def should_run_monitoring() -> bool:
    """
    检查是否应该运行 MONITORING 检查 (每7天一次)。

    Returns:
        True 如果应该运行监控检查
    """
    state_obj = load_state()
    if state_obj["state"] not in (ACTIVE, MONITORING):
        return False

    params = _load_params().get("state_machine", {})
    interval = params.get("monitor_check_interval_days", 7)

    last_check = state_obj.get("last_monitor_check")
    if not last_check:
        return True

    try:
        last_dt = datetime.fromisoformat(last_check)
        now = datetime.now(CN_TZ)
        days_since = (now - last_dt).days
        return days_since >= interval
    except Exception:
        return True


def record_monitor_check(result: dict):
    """记录一次监控检查结果"""
    state_obj = load_state()
    state_obj["last_monitor_check"] = datetime.now(CN_TZ).isoformat()
    state_obj["monitor_checks"] = state_obj.get("monitor_checks", 0) + 1
    state_obj.setdefault("monitor_history", []).append({
        "timestamp": datetime.now(CN_TZ).isoformat(),
        "result": result,
    })
    # 只保留最近20次
    state_obj["monitor_history"] = state_obj["monitor_history"][-20:]
    save_state(state_obj)


def get_state_summary() -> dict:
    """获取状态摘要 (供 Dashboard 使用)"""
    state_obj = load_state()
    s = state_obj["state"]
    behavior = STATE_BEHAVIOR.get(s, {})

    return {
        "state": s,
        "state_emoji": STATE_EMOJI.get(s, "❓"),
        "state_label": STATE_LABELS.get(s, s),
        "entered_at": state_obj.get("entered_at"),
        "degradation_count": state_obj.get("degradation_count", 0),
        "monitor_checks": state_obj.get("monitor_checks", 0),
        "last_monitor_check": state_obj.get("last_monitor_check"),
        "behavior": behavior,
        "can_trade": behavior.get("execute_trade", False),
        "history": state_obj.get("history", [])[-5:],  # 最近5次转换
    }


def reset_state(state: str = COLLECT_ONLY):
    """重置状态机 (仅用于调试/初始化)"""
    state_obj = {
        "state": state,
        "entered_at": datetime.now(CN_TZ).isoformat(),
        "history": [],
        "last_monitor_check": None,
        "monitor_checks": 0,
        "degradation_count": 0,
    }
    save_state(state_obj)
    logger.info(f"状态机已重置: {state}")


if __name__ == "__main__":
    # 调试: 打印当前状态
    summary = get_state_summary()
    print(f"当前状态: {summary['state_emoji']} {summary['state']}")
    print(f"标签: {summary['state_label']}")
    print(f"可交易: {'是' if summary['can_trade'] else '否'}")
    print(f"降级次数: {summary['degradation_count']}")
    print(f"监控检查次数: {summary['monitor_checks']}")
    if summary["history"]:
        print("\n最近状态转换:")
        for h in summary["history"]:
            print(f"  {h['from']} → {h['to']}: {h['reason']}")
