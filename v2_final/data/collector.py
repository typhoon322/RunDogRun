"""
v2_final/data/collector.py — 本地历史数据采集
================================================
AKShare → data/raw/ CSV 缓存 + 增量更新
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("v2.collector")

DATA_DIR = "data/raw"


def ensure_dir() -> None:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def save_stock_history(code: str, start_date: str = "20230101") -> str:
    """下载单只股票完整历史到本地 CSV"""
    ensure_dir()
    path = f"{DATA_DIR}/{code}.csv"

    try:
        import akshare as ak
        import pandas as pd

        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start_date, adjust="qfq")
        df = df.rename(columns={
            "日期": "date", "收盘": "close", "开盘": "open",
            "最高": "high", "最低": "low", "成交量": "volume", "涨跌幅": "pct",
        })
        df.to_csv(path, index=False)
        logger.info(f"  下载 {code}: {len(df)} 条 → {path}")
        return path
    except Exception as e:
        logger.warning(f"  下载 {code} 失败: {e}")
        return ""


def load_local_data(code: str):
    """读取本地 CSV (用于快速回测)"""
    path = f"{DATA_DIR}/{code}.csv"
    if not os.path.exists(path):
        return None
    import pandas as pd
    return pd.read_csv(path)


def is_cached(code: str) -> bool:
    return os.path.exists(f"{DATA_DIR}/{code}.csv")


def update_stock_data(code: str, days_threshold: int = 3) -> bool:
    """
    增量更新: 如果本地数据滞后超过N天, 重新拉取。

    Returns:
        True 如果发生了更新
    """
    path = f"{DATA_DIR}/{code}.csv"

    if not is_cached(code):
        save_stock_history(code)
        return True

    try:
        import pandas as pd
        old = pd.read_csv(path)
        if old.empty:
            save_stock_history(code)
            return True

        last_date = str(old["date"].max())
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        days_behind = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days

        if days_behind > days_threshold:
            # 只拉取增量
            import akshare as ak
            new = ak.stock_zh_a_hist(symbol=code, period="daily",
                                      start_date=last_date, adjust="qfq")
            if new is not None and not new.empty:
                new = new.rename(columns={
                    "日期": "date", "收盘": "close", "开盘": "open",
                    "最高": "high", "最低": "low", "成交量": "volume", "涨跌幅": "pct",
                })
                merged = pd.concat([old, new]).drop_duplicates(subset="date").sort_values("date")
                merged.to_csv(path, index=False)
                logger.info(f"  更新 {code}: +{len(new)} 条")
                return True
        return False
    except Exception as e:
        logger.warning(f"  更新 {code} 失败: {e}, 重新下载")
        save_stock_history(code)
        return True


def batch_collect(codes: list[str]) -> dict[str, str]:
    """批量采集 — 已有缓存则跳过"""
    ensure_dir()
    results = {}
    for code in codes:
        if not is_cached(code):
            path = save_stock_history(code)
        else:
            path = f"{DATA_DIR}/{code}.csv"
            update_stock_data(code)
        results[code] = path
    logger.info(f"数据仓库: {len(results)} 只股票本地就绪")
    return results


def get_cache_stats() -> dict:
    """统计本地缓存"""
    ensure_dir()
    files = list(Path(DATA_DIR).glob("*.csv"))
    total_size = sum(f.stat().st_size for f in files) / 1024  # KB
    return {
        "cached_stocks": len(files),
        "total_size_kb": round(total_size, 1),
    }
