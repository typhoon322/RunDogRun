"""
report/standard_report.py — V3 FINAL 统一统计格式
======================================================
所有分析必须用此格式输出。禁止自定义报表、禁止临时分析脚本。

输出:
  1. Score Bucket Report (分桶统计)
  2. System Health Report (系统健康)
"""
import json
import logging
import os

import pandas as pd

logger = logging.getLogger("v3.std_report")

SIGNALS_CSV = "data/signals/signals_with_returns.csv"
OUTPUT_FILE = "output/standard_report.json"

BUCKETS = [
    (0, 50, "0-50"),
    (50, 65, "50-65"),
    (65, 75, "65-75"),
    (75, 200, "75+"),
]


def generate() -> dict:
    """
    生成统一标准报告 — 唯一允许的报表格式。

    Returns:
        {
            "score_buckets": {...},
            "system_health": {...},
            "generated_at": iso_timestamp,
        }
    """
    if not os.path.exists(SIGNALS_CSV):
        return _empty()

    df = pd.read_csv(SIGNALS_CSV)
    col = "ret_5d"
    if col not in df.columns:
        return _empty()

    valid = df.dropna(subset=[col, "score"])
    if len(valid) < 3:
        return _empty()

    # ── Score Bucket Report ──
    buckets = {}
    for lo, hi, label in BUCKETS:
        sub = valid[(valid["score"] >= lo) & (valid["score"] < hi)]
        if len(sub) == 0:
            buckets[label] = {"avg_return": None, "win_rate": None, "n": 0}
            continue
        rets = sub[col]
        buckets[label] = {
            "avg_return": round(float(rets.mean()), 4),
            "win_rate": round(float((rets > 0).sum() / len(rets)), 3),
            "n": len(sub),
        }

    # ── System Health Report ──
    all_rets = valid[col]
    n = len(all_rets)
    wr = float((all_rets > 0).sum() / n)
    avg_r = float(all_rets.mean())
    cumulative = (1 + all_rets).cumprod()
    peak = cumulative.cummax()
    max_dd = float(((cumulative - peak) / peak).min())
    expectancy = round(avg_r * wr - abs(avg_r) * (1 - wr), 4)

    health = {
        "total_trades": n,
        "win_rate": round(wr, 3),
        "avg_return": round(avg_r, 4),
        "max_drawdown": round(max_dd, 4),
        "expectancy": expectancy,
    }

    report = {
        "score_buckets": buckets,
        "system_health": health,
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print()
    print("─" * 40)
    print("  📊 Standard Report")
    print("─" * 40)
    print(f"  交易次数: {n}  胜率: {wr:.0%}  期望值: {expectancy:+.3%}")
    print(f"  最大回撤: {max_dd:.1%}")
    for label, b in buckets.items():
        if b["n"] > 0:
            print(f"  {label}: n={b['n']:3d}  avg={b['avg_return']:+.3%}  wr={b['win_rate']:.0%}")
    print("─" * 40)

    return report


def _empty() -> dict:
    return {
        "score_buckets": {label: {"avg_return": None, "win_rate": None, "n": 0} for _, _, label in BUCKETS},
        "system_health": {"total_trades": 0, "win_rate": 0, "avg_return": 0, "max_drawdown": 0, "expectancy": 0},
        "generated_at": "",
    }
