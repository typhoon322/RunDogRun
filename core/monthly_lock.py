"""
core/monthly_lock.py — v3 FINAL 月度复盘锁定机制
=====================================================
防止系统被"情绪化频繁改坏"。
规则:
  1. 每30天才允许调整参数
  2. 必须基于30天数据才能改
  3. 修改必须记录版本
  4. 禁止临时调参
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.lock")

LOCK_FILE = "data/version_lock.json"
PARAMS_FILE = "data/current_params.json"

# ── 默认参数 ──
DEFAULT_PARAMS = {
    "trend_min": 65,
    "flow_min": 55,
    "score_buy": 70,
    "score_strong": 80,
    "score_caution": 60,
    "score_exit": 50,
    "trend_crash": 50,
    "flow_dry": 45,
    "cooling_days": 3,
    "position_70": 0.30,
    "position_75": 0.60,
    "position_80": 1.00,
}


def load_lock() -> dict:
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, encoding="utf-8") as f:
            return json.load(f)
    # 首次初始化
    lock = {
        "version": "v3.0-FINAL",
        "last_modified": datetime.now(CN_TZ).strftime("%Y-%m-%d"),
        "next_allowed": (datetime.now(CN_TZ) + timedelta(days=30)).strftime("%Y-%m-%d"),
        "change_log": [],
    }
    save_lock(lock)
    return lock


def save_lock(lock: dict):
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(lock, f, ensure_ascii=False, indent=2)


def can_modify() -> tuple[bool, str]:
    """检查是否允许修改参数"""
    lock = load_lock()
    today = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    next_allowed = lock.get("next_allowed", today)
    if today < next_allowed:
        return False, f"🔒 锁定中, 最早 {next_allowed} 可修改"
    return True, "✅ 可修改"


def propose_change(param_name: str, old_value, new_value, reason: str, data_evidence: str = "") -> dict:
    """提议参数变更 (需通过 can_modify 检查)"""
    ok, msg = can_modify()
    if not ok:
        return {"allowed": False, "reason": msg}

    lock = load_lock()
    entry = {
        "date": datetime.now(CN_TZ).strftime("%Y-%m-%d"),
        "param": param_name,
        "old": old_value,
        "new": new_value,
        "reason": reason,
        "evidence": data_evidence,
    }
    lock["change_log"].append(entry)
    lock["last_modified"] = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    lock["next_allowed"] = (datetime.now(CN_TZ) + timedelta(days=30)).strftime("%Y-%m-%d")
    save_lock(lock)

    logger.info(f"参数变更: {param_name} {old_value}→{new_value} ({reason})")
    return {"allowed": True, "entry": entry, "next_review": lock["next_allowed"]}


def get_current_params() -> dict:
    """获取当前生效参数"""
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE, encoding="utf-8") as f:
            return json.load(f)
    params = dict(DEFAULT_PARAMS)
    save_current_params(params)
    return params


def save_current_params(params: dict):
    os.makedirs(os.path.dirname(PARAMS_FILE), exist_ok=True)
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


def status() -> dict:
    """锁定状态摘要"""
    lock = load_lock()
    ok, msg = can_modify()
    return {
        "version": lock["version"],
        "last_modified": lock["last_modified"],
        "next_allowed": lock["next_allowed"],
        "can_modify": ok,
        "status_msg": msg,
        "total_changes": len(lock["change_log"]),
        "recent_changes": lock["change_log"][-3:] if lock["change_log"] else [],
    }
