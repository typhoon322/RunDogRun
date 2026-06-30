"""
execution/decision_engine.py — V3 FINAL 唯一决策引擎
=========================================================
所有交易必须经过此函数。禁止绕过。

INPUT:  trend, flow, value, system_score
OUTPUT: BUY_FULL / BUY_SMALL / NO_TRADE / EXIT / REDUCE

5 种决策:
  BUY_FULL   — 强买, 满仓 (score >= 80, gates pass)
  BUY_SMALL  — 小仓试单 (70 <= score < 80, gates pass)
  NO_TRADE   — 不交易, 持仓不动 (score ok 但 trend/flow 不足)
  REDUCE     — 减仓50% (50 <= score < 60)
  EXIT       — 清仓退出 (score < 50 或 趋势崩坏 或 流动性枯竭)

这是系统的"真理之源"——唯一允许修改决策逻辑的地方。
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.decision")

# ── 阈值 (优先从 config/params.yaml 读取, 回退到 constitution.json) ──

def _load_thresholds() -> dict:
    # V3: 优先从 params.yaml 读取
    try:
        import yaml
        path = "config/params.yaml"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            de = cfg.get("decision_engine", {})
            if de:
                return de
    except Exception:
        pass

    # 回退: constitution.json
    path = "data/constitution.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
        return c.get("thresholds", {})

    # 默认值
    return {
        "trend_min": 65, "flow_min": 55,
        "system_score_buy": 70, "system_score_strong": 80,
        "system_score_caution": 60, "system_score_exit": 50,
        "trend_crash": 50, "flow_dry": 45,
    }


def decide(
    system_score: float,
    trend: float,
    flow: float,
    value: float = 0,
) -> dict:
    """
    唯一决策入口 — 全系统所有交易必须通过这里。

    Returns:
        {
            "action": "BUY_FULL" | "BUY_SMALL" | "NO_TRADE" | "EXIT" | "REDUCE",
            "emoji": str,
            "reason": str,
            "allow_trade": bool,       # 是否允许开新仓
            "allow_hold": bool,        # 是否允许持有现有仓位
            "position_change": float,  # 仓位变化比例 (-1=清仓, -0.5=减半, 0=不动, +0.3=加30%)
            "inputs": {trend, flow, value, system_score},
            "thresholds": {当前生效的阈值},
            "decided_at": iso_timestamp,
        }
    """
    t = _load_thresholds()

    inputs = {
        "trend": round(trend, 1),
        "flow": round(flow, 1),
        "value": round(value, 1) if value else 0,
        "system_score": round(system_score, 1),
    }

    # ═══ Layer 1: 硬退出区 (EXIT) ═══
    # 趋势崩坏 / 流动性枯竭 / 系统极弱 → 强制清仓
    if trend < t["trend_crash"]:
        return _result("EXIT", "🔴",
                       f"趋势崩坏 EXIT (trend={trend:.0f}<{t['trend_crash']})",
                       inputs, t, allow_trade=False, allow_hold=False, pos_change=-1.0)
    if flow < t["flow_dry"]:
        return _result("EXIT", "🔴",
                       f"流动性枯竭 EXIT (flow={flow:.0f}<{t['flow_dry']})",
                       inputs, t, allow_trade=False, allow_hold=False, pos_change=-1.0)
    if system_score < t["system_score_exit"]:
        return _result("EXIT", "🔴",
                       f"系统强度 EXIT (score={system_score:.0f}<{t['system_score_exit']})",
                       inputs, t, allow_trade=False, allow_hold=False, pos_change=-1.0)

    # ═══ Layer 2: 减仓区 (REDUCE) ═══
    # 系统偏弱 → 减仓50%, 不开新仓
    if system_score < t["system_score_caution"]:
        return _result("REDUCE", "🟠",
                       f"减仓 REDUCE ({t['system_score_exit']}≤score={system_score:.0f}<{t['system_score_caution']})",
                       inputs, t, allow_trade=False, allow_hold=True, pos_change=-0.5)

    # ═══ Layer 3: 观望区 (NO_TRADE) ═══
    # Score 够了但 trend/flow 不足, 或 score 在 caution-buy 之间
    if system_score < t["system_score_buy"]:
        return _result("NO_TRADE", "🟡",
                       f"观望 NO_TRADE ({t['system_score_caution']}≤score={system_score:.0f}<{t['system_score_buy']})",
                       inputs, t, allow_trade=False, allow_hold=True, pos_change=0.0)

    # trend/flow 门槛 (Hard Gate)
    if trend < t["trend_min"] or flow < t["flow_min"]:
        reasons = []
        if trend < t["trend_min"]:
            reasons.append(f"趋势不足 (trend={trend:.0f}<{t['trend_min']})")
        if flow < t["flow_min"]:
            reasons.append(f"流动性不足 (flow={flow:.0f}<{t['flow_min']})")
        return _result("NO_TRADE", "🟡",
                       f"观望 NO_TRADE — {', '.join(reasons)}",
                       inputs, t, allow_trade=False, allow_hold=True, pos_change=0.0)

    # ═══ Layer 4: 买入区 ═══
    if system_score >= t["system_score_strong"]:
        return _result("BUY_FULL", "🟢",
                       f"强买 BUY_FULL (score={system_score:.0f}≥{t['system_score_strong']})",
                       inputs, t, allow_trade=True, allow_hold=True, pos_change=0.6)

    return _result("BUY_SMALL", "🟢",
                   f"小仓试单 BUY_SMALL ({t['system_score_buy']}≤score={system_score:.0f}<{t['system_score_strong']})",
                   inputs, t, allow_trade=True, allow_hold=True, pos_change=0.3)


# ── 动作常量 (供外部引用) ──
ACTIONS = {
    "EXIT":      {"emoji": "🔴", "label": "清仓退出",  "allow_trade": False, "allow_hold": False, "pos_change": -1.0},
    "REDUCE":    {"emoji": "🟠", "label": "减仓50%",   "allow_trade": False, "allow_hold": True,  "pos_change": -0.5},
    "NO_TRADE":  {"emoji": "🟡", "label": "观望不动",  "allow_trade": False, "allow_hold": True,  "pos_change": 0.0},
    "BUY_SMALL": {"emoji": "🟢", "label": "小仓试单",  "allow_trade": True,  "allow_hold": True,  "pos_change": 0.3},
    "BUY_FULL":  {"emoji": "🟢", "label": "满仓买入",  "allow_trade": True,  "allow_hold": True,  "pos_change": 0.6},
}


def _result(
    action: str, emoji: str, reason: str,
    inputs: dict, thresholds: dict,
    allow_trade: bool = False, allow_hold: bool = True, pos_change: float = 0.0,
) -> dict:
    return {
        "action": action,
        "emoji": emoji,
        "reason": reason,
        "allow_trade": allow_trade,
        "allow_hold": allow_hold,
        "position_change": pos_change,
        "inputs": inputs,
        "thresholds": thresholds,
        "decided_at": datetime.now(CN_TZ).isoformat(),
    }
