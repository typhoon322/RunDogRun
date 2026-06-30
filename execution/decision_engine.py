"""
execution/decision_engine.py — V3 FINAL 唯一决策引擎
=========================================================
所有交易必须经过此函数。禁止绕过。

INPUT:  trend, flow, value, system_score
OUTPUT: BUY_FULL / BUY_SMALL / WATCH / NO_TRADE

这是系统的"真理之源"——唯一允许修改决策逻辑的地方。
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.decision")

# ── 阈值 (从 constitution.json 读取, 不允许硬编码) ──

def _load_thresholds() -> dict:
    path = "data/constitution.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
        return c.get("thresholds", {})
    # fallback
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
            "action": "BUY_FULL" | "BUY_SMALL" | "WATCH" | "NO_TRADE",
            "emoji": "🟢" | "🟡" | "🔴",
            "reason": str,
            "allow_trade": bool,
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

    # Layer 1: 硬禁止区
    if trend < t["trend_crash"]:
        return _result("NO_TRADE", "🔴", f"趋势崩坏 (trend={trend:.0f}<{t['trend_crash']})", inputs, t)
    if flow < t["flow_dry"]:
        return _result("NO_TRADE", "🔴", f"流动性枯竭 (flow={flow:.0f}<{t['flow_dry']})", inputs, t)

    # Layer 2: 分数判定
    if system_score < t["system_score_exit"]:
        return _result("NO_TRADE", "🔴", f"系统强度<{t['system_score_exit']}, 强制空仓", inputs, t)

    if system_score < t["system_score_caution"]:
        return _result("WATCH", "🟡", f"观望: {t['system_score_exit']}≤score<{t['system_score_caution']}", inputs, t)

    if system_score < t["system_score_buy"]:
        return _result("WATCH", "🟡", f"观察: {t['system_score_caution']}≤score<{t['system_score_buy']}", inputs, t)

    # Layer 3: 趋势+流动性门槛 (Hard Gate)
    if trend < t["trend_min"] or flow < t["flow_min"]:
        reasons = []
        if trend < t["trend_min"]:
            reasons.append(f"趋势不足 (trend={trend:.0f}<{t['trend_min']})")
        if flow < t["flow_min"]:
            reasons.append(f"流动性不足 (flow={flow:.0f}<{t['flow_min']})")
        return _result("WATCH", "🟡", ", ".join(reasons), inputs, t)

    # Layer 4: 买入判定
    if system_score >= t["system_score_strong"]:
        return _result("BUY_FULL", "🟢", f"强买: score={system_score:.0f}≥{t['system_score_strong']}", inputs, t)

    return _result("BUY_SMALL", "🟢", f"小买: {t['system_score_buy']}≤score={system_score:.0f}<{t['system_score_strong']}", inputs, t)


def _result(action: str, emoji: str, reason: str, inputs: dict, thresholds: dict) -> dict:
    return {
        "action": action,
        "emoji": emoji,
        "reason": reason,
        "allow_trade": action in ("BUY_FULL", "BUY_SMALL"),
        "inputs": inputs,
        "thresholds": thresholds,
        "decided_at": datetime.now(CN_TZ).isoformat(),
    }
