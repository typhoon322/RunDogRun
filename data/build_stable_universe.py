"""
data/build_stable_universe.py — 稳定版 Universe 生成器
===========================================================
raw_universe() → merge(旧+新) → 平滑输出
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.build_rotating_universe import build_universe as raw_universe
from core.stable_universe import load_old, merge_universe


def build_stable(top_n: int = 300) -> list[str]:
    """生成稳定 Universe: 旧池 + 新信号 平滑合并"""
    old = load_old()
    new = raw_universe(top_n=top_n, top_sectors=3)

    if not new:
        return old or []

    final = merge_universe(old, new, max_size=top_n)
    return final


if __name__ == "__main__":
    codes = build_stable()
    print(f"Stable Universe: {len(codes)} 只")
