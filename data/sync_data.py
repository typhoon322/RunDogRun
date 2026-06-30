"""
data/sync_data.py — 数据自动补齐系统
=========================================
Universe 新增股票 → 自动补 180 天历史 CSV
v3.1: 使用 ProviderFactory 可插拔多数据源
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.provider_factory import get_factory

DATA_DIR = "data/raw/daily"


def sync_stock(code: str, retries: int = 0) -> str | None:
    """拉取单只股票数据, 主源失败自动切备源 (factory 内部已做 failover)"""
    import os as _os
    factory = get_factory()
    try:
        df = factory.fetch_history(code)
        if df is not None and not df.empty:
            df = df.tail(180)
            _os.makedirs(DATA_DIR, exist_ok=True)
            path = f"{DATA_DIR}/{code}.csv"
            df.to_csv(path, index=False)
            return path
    except Exception:
        pass
    return None


def need_update(code: str) -> bool:
    """检查是否需要更新数据"""
    path = f"{DATA_DIR}/{code}.csv"
    if not os.path.exists(path):
        return True
    if os.path.getsize(path) < 10:
        return True
    import pandas as pd
    try:
        df = pd.read_csv(path)
        return len(df) < 150
    except Exception:
        return True


def sync_universe(codes: list[str], max_new: int = 30) -> dict:
    """
    检查并补齐缺失数据。只处理新股票(最多 max_new 只避免API过载)。
    使用并发线程池加速同步 (4线程), 每线程内部顺序请求各数据源。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 先筛出需要同步的
    to_sync = [c for c in codes if need_update(c)][:max_new]
    skip = len(codes) - len(to_sync)

    if not to_sync:
        print(f"数据同步: 0 新增, {skip} 已有缓存")
        return {"new": 0, "skip": skip}

    ok = 0
    failed = []

    def _sync_one(code: str) -> tuple[str, bool]:
        try:
            path = sync_stock(code)
            return (code, path is not None)
        except Exception:
            return (code, False)

    # 4线程并发, 每个线程内 factory 顺序尝试各数据源
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_sync_one, c): c for c in to_sync}
        for future in as_completed(futures):
            code, success = future.result()
            if success:
                ok += 1
            else:
                failed.append(code)

    if failed:
        print(f"  ⚠️ {len(failed)} 只同步失败: {failed[:5]}{'...' if len(failed) > 5 else ''}")
    print(f"数据同步: {ok} 新增, {skip} 已有缓存, {len(failed)} 失败")
    return {"new": ok, "skip": skip, "failed": len(failed)}
