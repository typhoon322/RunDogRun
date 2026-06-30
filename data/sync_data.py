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


def sync_stock(code: str, retries: int = 2) -> str | None:
    """拉取单只股票数据, 主源失败自动切备源, 最多重试2次"""
    factory = get_factory()
    last_error = None
    for attempt in range(retries + 1):
        try:
            df = factory.fetch_history(code)
            if df is None or df.empty:
                raise ValueError("空数据")
            df = df.tail(180)
            os.makedirs(DATA_DIR, exist_ok=True)
            path = f"{DATA_DIR}/{code}.csv"
            df.to_csv(path, index=False)
            return path
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(2)
    raise last_error


def sync_universe(codes: list[str], max_new: int = 30) -> dict:
    """
    检查并补齐缺失数据。只处理新股票(最多 max_new 只避免API过载)。
    每只股票之间间隔1.5秒，防止东方财富反爬限流。
    """
    import time
    ok = 0
    skip = 0
    for code in codes:
        if not need_update(code):
            skip += 1
            continue
        if ok >= max_new:
            break
        try:
            path = sync_stock(code)
            if path:
                ok += 1
            time.sleep(1.5)  # 请求间隔，防止反爬
        except Exception as e:
            print(f"  ❌ {code}: {e}")
    print(f"数据同步: {ok} 新增, {skip} 已有缓存")
    return {"new": ok, "skip": skip}
