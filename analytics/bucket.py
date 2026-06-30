"""
analytics/bucket.py — v3 FINAL 评分分桶分析器
==================================================
Score 4 桶: [0-50, 50-65, 65-75, 75+]  (对齐 V3 FINAL spec)
每桶输出: avg_return, win_rate, sample_size
"""
import json
import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger("v3.bucket")

SIGNALS_CSV = "data/signals/signals_with_returns.csv"
BUCKETS = [
    (0, 50, "🔴 0-50"),
    (50, 65, "🟠 50-65"),
    (65, 75, "🟡 65-75"),
    (75, 200, "🟢 75+"),
]


def analyze(df: pd.DataFrame, horizon: int = 5) -> dict:
    """分桶分析"""
    col = f"ret_{horizon}d"
    if col not in df.columns:
        return {"error": f"无 ret_{horizon}d 列"}
    valid = df.dropna(subset=[col, "score"])
    if len(valid) < 10:
        return {"error": "数据不足"}

    results = []
    for lo, hi, label in BUCKETS:
        sub = valid[(valid["score"] >= lo) & (valid["score"] < hi)]
        if len(sub) == 0:
            results.append({"bucket": label, "n": 0})
            continue
        rets = sub[col]
        win = (rets > 0).sum() / len(rets) if len(rets) > 0 else 0
        avg_r = float(rets.mean())
        std_r = float(rets.std()) if len(rets) > 1 else 0
        sharpe_r = round(avg_r / std_r * (252 ** 0.5), 2) if std_r > 0 else 0
        # max drawdown
        cumulative = (1 + rets).cumprod()
        peak = cumulative.cummax()
        dd = (cumulative - peak) / peak
        max_dd = float(dd.min())

        results.append({
            "bucket": label,
            "count": len(sub),
            "avg_return": round(avg_r, 4),
            "win_rate": round(float(win), 3),
            "sharpe": sharpe_r,
            "max_drawdown": round(max_dd, 4),
        })

    return {"horizon": f"{horizon}d", "buckets": results, "total_signals": len(valid)}


def bucket_report() -> dict:
    """完整分桶报告"""
    if not os.path.exists(SIGNALS_CSV):
        logger.warning("无信号数据")
        return {"error": "无信号数据, 请先运行 forward_returns.compute()"}

    df = pd.read_csv(SIGNALS_CSV)
    report = analyze(df, horizon=5)

    # 打印
    print()
    print("─" * 50)
    print(f"  📊 分桶分析 — {report.get('total_signals', 0)} 条信号")
    print("─" * 50)
    for b in report.get("buckets", []):
        if b.get("count", 0) == 0:
            continue
        print(f"  {b['bucket']}: n={b['count']:3d}  "
              f"avg={b['avg_return']:+.3%}  wr={b['win_rate']:.0%}  "
              f"sharpe={b['sharpe']}  dd={b['max_drawdown']:.1%}")
    print("─" * 50)

    # 保存
    os.makedirs("output", exist_ok=True)
    with open("output/bucket_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    bucket_report()
