"""
v2_final/data/snapshot.py — 数据快照系统
============================================
每天冷冻一份 data/raw/daily/ → data/snapshots/YYYY-MM-DD/
保证回测永远基于同一份数据, 可复现
"""
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("v2.snapshot")

SNAPSHOT_DIR = "data/snapshots"


def create_snapshot(date_str: str | None = None) -> str:
    """
    创建今日数据快照。

    Returns:
        快照路径
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    src = "data/raw/daily"
    dst = f"{SNAPSHOT_DIR}/{date_str}"

    if not os.path.exists(src):
        logger.warning("data/raw/daily 不存在, 跳过快照")
        return ""

    os.makedirs(dst, exist_ok=True)

    count = 0
    for f in os.listdir(src):
        if f.endswith(".csv"):
            shutil.copy(f"{src}/{f}", f"{dst}/{f}")
            count += 1

    # 元数据
    meta = {
        "date": date_str,
        "files": count,
        "created_at": datetime.now().isoformat(),
        "source": src,
    }
    with open(f"{dst}/index.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    logger.info(f"快照 {date_str}: {count} 文件 → {dst}")
    return dst


def load_snapshot(date_str: str) -> str | None:
    """加载指定日期的快照路径"""
    path = f"{SNAPSHOT_DIR}/{date_str}"
    if os.path.exists(path):
        return path
    return None


def list_snapshots() -> list[str]:
    """列出所有快照日期"""
    if not os.path.exists(SNAPSHOT_DIR):
        return []
    snaps = sorted([d for d in os.listdir(SNAPSHOT_DIR)
                    if os.path.isdir(f"{SNAPSHOT_DIR}/{d}")], reverse=True)
    return snaps


def get_latest_snapshot() -> str | None:
    """获取最近一次快照日期"""
    snaps = list_snapshots()
    return snaps[0] if snaps else None
