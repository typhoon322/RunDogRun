"""
signals/snapshot.py — V3 FINAL 信号快照锁定
===============================================
信号生成后不可修改。locked=true 为强制约束。
Future return 只能追加，不能回写到 snapshot。
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.snapshot")

SNAPSHOT_DIR = "data/signals/snapshots"


def create_snapshot(
    stock_code: str,
    stock_name: str,
    decision: dict,
    entry_price: float,
) -> dict:
    """
    冻结信号状态 — 生成后不可修改。

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        decision: decision_engine.decide() 的返回值
        entry_price: 入场价格

    Returns:
        不可变快照 dict
    """
    now = datetime.now(CN_TZ)
    snapshot = {
        "timestamp": now.strftime("%Y-%m-%d"),
        "ticker": str(stock_code).zfill(6),
        "name": stock_name,
        "snapshot": {
            "trend": decision["inputs"]["trend"],
            "flow": decision["inputs"]["flow"],
            "value": decision["inputs"]["value"],
            "system_score": decision["inputs"]["system_score"],
        },
        "decision": decision["action"],
        "price": entry_price,
        "locked": True,
        "created_at": now.isoformat(),
    }

    # 持久化到磁盘
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOT_DIR, f"{snapshot['timestamp']}_{stock_code}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return snapshot


def load_snapshots(date_str: str | None = None) -> list[dict]:
    """读取快照历史"""
    if not os.path.exists(SNAPSHOT_DIR):
        return []
    snapshots = []
    for f in sorted(os.listdir(SNAPSHOT_DIR)):
        if not f.endswith(".json"):
            continue
        if date_str and not f.startswith(date_str):
            continue
        with open(os.path.join(SNAPSHOT_DIR, f), encoding="utf-8") as fp:
            snapshots.append(json.load(fp))
    return snapshots
