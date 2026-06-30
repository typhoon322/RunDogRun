"""
analytics/forward_returns.py — v3.0 前瞻收益引擎
=====================================================
读取 signals.jsonl → 对每条信号计算 ret_1d/5d/10d/20d → 输出 CSV
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_registry import DataRegistry

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.fwd")

SIGNAL_LOG = "logs/signals.jsonl"
OUTPUT_FILE = "data/signals/signals_with_returns.csv"
HORIZONS = [1, 5, 10, 20]


def compute():
    """计算所有历史信号的前瞻收益并输出 CSV"""
    if not os.path.exists(SIGNAL_LOG):
        logger.warning("无信号日志, 跳过")
        return None

    registry = DataRegistry()
    signals = []
    with open(SIGNAL_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not signals:
        return None

    df = pd.DataFrame(signals)
    logger.info(f"处理 {len(df)} 条信号, {df['stock_code'].nunique()} 只股票")

    # 对每只股票批量计算前瞻收益
    all_rows = []
    for code, group in df.groupby("stock_code"):
        dates = group["signal_date"].tolist()
        fwd = registry.get_forward_returns(str(code).zfill(6), dates, HORIZONS)
        for _, row in group.iterrows():
            sd = row["signal_date"]
            rets = fwd.get(sd, {})
            row_dict = row.to_dict()
            for h in HORIZONS:
                row_dict[f"ret_{h}d"] = rets.get(f"ret_{h}d", None)
            all_rows.append(row_dict)

    result = pd.DataFrame(all_rows)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    result.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    logger.info(f"前瞻收益已输出: {len(result)} 条 → {OUTPUT_FILE}")

    # 统计摘要
    valid = result.dropna(subset=[f"ret_{h}d" for h in HORIZONS], how="all")
    print(f"📈 前瞻收益: {len(valid)}/{len(result)} 条有效")
    for h in HORIZONS:
        col = f"ret_{h}d"
        vals = valid[col].dropna()
        if len(vals) > 0:
            print(f"  ret_{h}d: mean={vals.mean():+.3%}  median={vals.median():+.3%}  "
                  f"win={((vals>0).sum()/len(vals)):.0%}")

    return result


if __name__ == "__main__":
    compute()
