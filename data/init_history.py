"""
data/init_history.py — 批量初始化历史数据仓库
===================================================
从 AKShare 拉取 180 天日线 → data/raw/daily/*.csv
"""
import os
import sys
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

DATA_DIR = "data/raw/daily"
DAYS = 180

# 股票池: 核心标的 + 常用回测股
UNIVERSE = [
    "000001",  # 平安银行
    "600036",  # 招商银行
    "601398",  # 工商银行
    "600519",  # 贵州茅台
    "000858",  # 五粮液
    "300750",  # 宁德时代
    "600030",  # 中信证券
    "000333",  # 美的集团
    "000651",  # 格力电器
    "002594",  # 比亚迪
    "601318",  # 中国平安
    "600276",  # 恒瑞医药
    "601012",  # 隆基绿能
    "002475",  # 立讯精密
    "300059",  # 东方财富
    "600900",  # 长江电力
    "000002",  # 万科A
    "601166",  # 兴业银行
    "600887",  # 伊利股份
    "002415",  # 海康威视
]

start_date = (datetime.now() - timedelta(days=DAYS + 30)).strftime("%Y%m%d")

print(f"数据初始化: {len(UNIVERSE)} 只股票, 起始 {start_date}")
os.makedirs(DATA_DIR, exist_ok=True)

ok = 0
fail = 0

for code in UNIVERSE:
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start_date, adjust="qfq")
        df = df.tail(DAYS)
        df = df.rename(columns={
            "日期": "date", "收盘": "close", "开盘": "open",
            "最高": "high", "最低": "low", "成交量": "volume", "涨跌幅": "pct",
        })
        path = f"{DATA_DIR}/{code}.csv"
        df.to_csv(path, index=False)
        print(f"  ✅ {code} {len(df)}条 → {path}")
        ok += 1
    except Exception as e:
        print(f"  ❌ {code} 失败: {e}")
        fail += 1

print(f"\n完成: {ok} 成功, {fail} 失败 → {DATA_DIR}/")
