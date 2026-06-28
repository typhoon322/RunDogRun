"""
core/stable_universe.py — v2.5.5 Universe 稳定性控制器
=============================================================
平滑合并: 旧池70%保留 + 新池30%补充, 每次换仓≤20%
"""
import json
import logging
import os
from typing import Any

logger = logging.getLogger("v2.stable_universe")

CACHE_FILE = "data/universe_cache.json"
MAX_SIZE = 300
MAX_CHANGE_RATIO = 0.20   # 每次最多替换 20%


def load_old() -> list[str]:
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_universe(codes: list[str]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def merge_universe(
    old_codes: list[str],
    new_codes: list[str],
    max_size: int = MAX_SIZE,
    max_change: float = MAX_CHANGE_RATIO,
) -> list[str]:
    """
    稳定性平滑合并。

    规则:
      1. 交集 (稳定核心) — 保留
      2. 新增 — 最多 max_change * max_size 只
      3. 旧股 (仅旧池有) — 优先保留
      4. 最终补齐到 max_size
    """
    old_set = set(old_codes)
    new_set = set(new_codes)

    # 稳定核心: 两池都有
    stable = list(old_set & new_set)

    # 新增候选: 仅新池有
    fresh = list(new_set - old_set)
    max_new = int(max_size * max_change)
    fresh = fresh[:max_new]

    # 旧股保留: 仅旧池有
    legacy = list(old_set - new_set)

    # 组装
    final = list(dict.fromkeys(stable + fresh + legacy))
    final = final[:max_size]

    changed = len(set(final) - old_set) if old_set else len(final)
    logger.info(f"Universe: {len(old_set)}→{len(final)} "
                f"(stable={len(stable)}, new={len(fresh)}, changed={changed})")

    save_universe(final)
    return final


def apply_stability_score(
    old_codes: list[str],
    candidates: list[dict],
) -> list[dict]:
    """
    稳定性加权评分: 旧池股票 +3 分奖励。
    """
    old_set = set(old_codes)
    for c in candidates:
        code = c.get("code", "")
        if code in old_set:
            c["score"] = c.get("score", 0) + 3
        else:
            c["score"] = c.get("score", 0) + 1
    return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
