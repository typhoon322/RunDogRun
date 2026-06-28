"""
data/universe_loader.py — 从 Registry 派生 Universe
=======================================================
不再凭空生成, 而是从已有 CSV 数据仓库中选取
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_registry import DataRegistry


def load_universe(max_size: int = 300) -> list[str]:
    """直接从 DataRegistry 获取全部可用股票代码作为 Universe"""
    registry = DataRegistry()
    all_codes = registry.get_all()
    return all_codes[:max_size]


def load_universe_by_cache(max_size: int = 300) -> list[str]:
    """从已有的 CSV 缓存生成 Universe (保证回测数据一致性)"""
    return load_universe(max_size)


if __name__ == "__main__":
    codes = load_universe()
    print(f"Universe from Registry: {len(codes)} 只")
    print(f"Sample: {codes[:5]}")
