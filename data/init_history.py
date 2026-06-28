"""
data/init_history.py — 批量初始化历史数据仓库 (300股版)
===========================================================
支持分批拉取，避免 API 被封。默认每批 20 只，间隔 3 秒。
"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.universe_300 import UNIVERSE

import akshare as ak
import pandas as pd

DATA_DIR = "data/raw/daily"
DAYS = 180
BATCH_SIZE = 20
BATCH_SLEEP = 3  # 批次间隔秒数

start_date = (datetime.now() - timedelta(days=DAYS + 30)).strftime("%Y%m%d")
total = len(UNIVERSE)
os.makedirs(DATA_DIR, exist_ok=True)

print(f"数据初始化: {total} 只, 每批 {BATCH_SIZE}, 起始 {start_date}")
print(f"预计 {total // BATCH_SIZE + 1} 批, 约 {total * 1.5:.0f}s\n")

ok = 0
fail = 0
skip = 0

for batch_num in range(0, total, BATCH_SIZE):
    batch = UNIVERSE[batch_num:batch_num + BATCH_SIZE]
    bno = batch_num // BATCH_SIZE + 1
    print(f"--- 批次 {bno}/{total // BATCH_SIZE + 1} ({len(batch)}只) ---")

    for code in batch:
        path = f"{DATA_DIR}/{code}.csv"
        if os.path.exists(path):
            skip += 1
            continue

        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                     start_date=start_date, adjust="qfq")
            df = df.tail(DAYS)
            if df.empty:
                fail += 1
                continue
            df = df.rename(columns={
                "日期": "date", "收盘": "close", "开盘": "open",
                "最高": "high", "最低": "low", "成交量": "volume", "涨跌幅": "pct",
            })
            df.to_csv(path, index=False)
            ok += 1
        except Exception as e:
            fail += 1
            if "429" in str(e) or "too many" in str(e).lower():
                print(f"  ⚠️ 触发限流, 等待 30s...")
                time.sleep(30)

    if batch_num + BATCH_SIZE < total:
        time.sleep(BATCH_SLEEP)

print(f"\n{'='*40}")
print(f"完成: {ok} 新增, {skip} 已有缓存, {fail} 失败 → {DATA_DIR}/")
