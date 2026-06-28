"""
core/data_registry.py — v2.8 数据调度登记系统
=================================================
统一回答: CSV 有没有被 Universe 选中? 回测有没有实际使用?
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("v2.registry")

DATA_DIR = "data/raw/daily"
REGISTRY_PATH = "data/registry.json"


def get_csv_list() -> set[str]:
    """所有本地 CSV 代码"""
    if not os.path.exists(DATA_DIR):
        return set()
    return set(f.replace(".csv", "") for f in os.listdir(DATA_DIR) if f.endswith(".csv"))


def load_registry() -> dict[str, Any]:
    """读取上次登记的调度记录"""
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"csv_total": 0, "universe_count": 0, "used_count": 0, "history": []}


def save_registry(data: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def audit(universe: list[str], used_in_backtest: set[str]) -> dict[str, Any]:
    """
    三重审计: CSV → Universe → 回测使用。

    Returns:
        {csv_count, universe_count, used_count,
         unused_csv, missing_data, absorption_pct}
    """
    csv_set = get_csv_list()
    uni_set = set(universe)

    # 交叉统计
    csv_in_universe = csv_set & uni_set          # CSV 且被 Universe 选中
    csv_not_in_universe = csv_set - uni_set      # CSV 但未被选中
    uni_no_csv = uni_set - csv_set               # Universe 有但 CSV 缺

    used = used_in_backtest & csv_set
    unused_csv = csv_set - used_in_backtest

    absorption = round(len(csv_in_universe) / max(1, len(csv_set)) * 100, 1)
    utilization = round(len(used) / max(1, len(universe)) * 100, 1) if universe else 0

    result = {
        "csv_total": len(csv_set),
        "universe_count": len(universe),
        "used_in_backtest": len(used),
        "csv_in_universe": len(csv_in_universe),
        "csv_not_used": len(csv_not_in_universe),
        "uni_missing_data": len(uni_no_csv),
        "absorption_pct": absorption,       # CSV 被 Universe 吸收率
        "utilization_pct": utilization,     # Universe 被回测使用率
        "unused_csv": list(unused_csv)[:20],
        "missing_csv": list(uni_no_csv)[:10],
    }

    # 持久化
    registry = load_registry()
    registry.update({
        "csv_total": len(csv_set),
        "universe_count": len(universe),
        "used_count": len(used),
        "last_audit": result,
    })
    registry.setdefault("history", []).append({
        "time": __import__("datetime").datetime.now().isoformat(),
        "absorption": absorption,
        "utilization": utilization,
    })
    save_registry(registry)

    logger.info(f"数据审计: CSV{len(csv_set)}→Universe{len(universe)}→回测{len(used)} "
                f"(吸收{absorption}%, 利用{utilization}%)")
    return result


def health_summary() -> dict[str, Any]:
    """系统健康总览"""
    csv_set = get_csv_list()
    registry = load_registry()
    history = registry.get("history", [])

    # 趋势: 最近5次
    recent = history[-5:]
    trend = "stable →"
    if len(recent) >= 2:
        if recent[-1].get("absorption", 0) < recent[0].get("absorption", 0) - 5:
            trend = "declining ↘"
        elif recent[-1].get("absorption", 0) > recent[0].get("absorption", 0) + 3:
            trend = "improving ↗"

    return {
        "csv_files": len(csv_set),
        "registry_history": len(history),
        "trend": trend,
        "recent": recent[-3:],
        "status": "HEALTHY ✅" if len(csv_set) > 100 and not registry.get("last_audit", {}).get("missing_csv") else "OK ⚡",
    }
