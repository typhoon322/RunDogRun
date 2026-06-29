"""
core/data_days.py — 数据仓库交易日统计
==========================================
扫描 data/raw/daily/ 全部 CSV, 汇总交易日并缓存到 data/collection_days.json
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import pandas as pd

logger = logging.getLogger("data_days")

DATA_DIR = "data/raw/daily"
OUTPUT_FILE = "data/collection_days.json"

CN_TZ = timezone(timedelta(hours=8))


def compute_collection_days() -> dict:
    """
    扫描所有 CSV, 汇总交易日信息。

    Returns:
        {
            "csv_count": 414,
            "total_trading_days": 180,
            "date_range": "2025-09-23 ~ 2026-06-26",
            "first_date": "2025-09-23",
            "last_date": "2026-06-26",
            "updated_at": "2026-06-29T18:20:00+08:00",
            "per_stock_stats": {
                "max_days": 180,
                "min_days": 45,
                "avg_days": 175.3,
            }
        }
    """
    if not os.path.exists(DATA_DIR):
        return _empty_result()

    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    if not files:
        return _empty_result()

    all_dates: set[str] = set()
    stock_days: list[int] = []
    first_date = None
    last_date = None

    for f in files:
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, f), usecols=["日期"])
            dates = df["日期"].dropna().astype(str).tolist()
            dates = [d.strip() for d in dates if d.strip()]
            if dates:
                stock_days.append(len(dates))
                all_dates.update(dates)
                if first_date is None or dates[0] < first_date:
                    first_date = dates[0]
                if last_date is None or dates[-1] > last_date:
                    last_date = dates[-1]
        except Exception:
            continue

    sorted_dates = sorted(all_dates)

    return {
        "csv_count": len(files),
        "total_trading_days": len(sorted_dates),
        "date_range": f"{first_date} ~ {last_date}" if first_date and last_date else "",
        "first_date": first_date or "",
        "last_date": last_date or "",
        "updated_at": datetime.now(CN_TZ).isoformat(),
        "per_stock_stats": {
            "max_days": max(stock_days) if stock_days else 0,
            "min_days": min(stock_days) if stock_days else 0,
            "avg_days": round(sum(stock_days) / len(stock_days), 1) if stock_days else 0,
        },
    }


def save_collection_days():
    """计算并保存交易日统计"""
    result = compute_collection_days()
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"交易日统计已保存: {result['total_trading_days']}天 → {OUTPUT_FILE}")
    return result


def _empty_result() -> dict:
    return {
        "csv_count": 0,
        "total_trading_days": 0,
        "date_range": "",
        "first_date": "",
        "last_date": "",
        "updated_at": datetime.now(CN_TZ).isoformat(),
        "per_stock_stats": {"max_days": 0, "min_days": 0, "avg_days": 0},
    }


if __name__ == "__main__":
    r = save_collection_days()
    print(f"CSV: {r['csv_count']} 只")
    print(f"交易日: {r['total_trading_days']} 天")
    print(f"范围: {r['date_range']}")
    print(f"每只: 最多{r['per_stock_stats']['max_days']}天 / 最少{r['per_stock_stats']['min_days']}天 / 平均{r['per_stock_stats']['avg_days']}天")
