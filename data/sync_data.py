"""
data/sync_data.py — 数据自动补齐系统
=========================================
Universe 新增股票 → 自动补 180 天历史 CSV
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = "data/raw/daily"


def fetch_stock(code: str):
    import akshare as ak
    return ak.stock_zh_a_hist(symbol=code, period="daily",
                               start_date="20240101", adjust="qfq")


def need_update(code: str) -> bool:
    path = f"{DATA_DIR}/{code}.csv"
    if not os.path.exists(path):
        return True
    import pandas as pd
    df = pd.read_csv(path)
    return len(df) < 150


def sync_stock(code: str) -> str:
    df = fetch_stock(code)
    df = df.tail(180)
    os.makedirs(DATA_DIR, exist_ok=True)
    path = f"{DATA_DIR}/{code}.csv"
    df.to_csv(path, index=False)
    return path


def sync_universe(codes: list[str], max_new: int = 50) -> dict:
    """
    检查并补齐缺失数据。只处理新股票(最多 max_new 只避免API过载)。
    """
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
            ok += 1
        except Exception as e:
            print(f"  ❌ {code}: {e}")
    print(f"数据同步: {ok} 新增, {skip} 已有缓存")
    return {"new": ok, "skip": skip}
