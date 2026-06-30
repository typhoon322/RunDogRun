"""
analytics/ic.py — v3.0 IC/IR 计算引擎
===========================================
Pearson IC / Spearman Rank IC / Rolling IC / IC Decay
"""
import json
import logging
import os

import numpy as np
import pandas as pd

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger_warn = logging.getLogger("v3.ic")
    logger_warn.warning("scipy 未安装, IC 计算将降级为简易版")

logger = logging.getLogger("v3.ic")

SIGNALS_CSV = "data/signals/signals_with_returns.csv"


def load_signals() -> pd.DataFrame | None:
    if not os.path.exists(SIGNALS_CSV):
        logger.warning("无信号数据, 请先运行 forward_returns.compute()")
        return None
    return pd.read_csv(SIGNALS_CSV)


def calc_ic(df: pd.DataFrame, horizon: int = 5) -> dict:
    """Pearson IC: corr(score, forward_return)"""
    col = f"ret_{horizon}d"
    if col not in df.columns:
        return {"ic": None, "error": f"无 ret_{horizon}d 列"}
    valid = df[[col, "score"]].dropna()
    if len(valid) < 5:
        return {"ic": None, "error": f"仅 {len(valid)} 条有效数据"}
    if HAS_SCIPY:
        ic, pval = stats.pearsonr(valid["score"], valid[col])
    else:
        ic = float(valid["score"].corr(valid[col]))
        pval = None
    return {"ic": round(float(ic), 4), "p_value": round(float(pval), 4) if pval else None, "n": len(valid)}


def calc_rank_ic(df: pd.DataFrame, horizon: int = 5) -> dict:
    """Spearman Rank IC"""
    col = f"ret_{horizon}d"
    if col not in df.columns:
        return {"rank_ic": None, "error": f"无 ret_{horizon}d 列"}
    valid = df[[col, "score"]].dropna()
    if len(valid) < 5:
        return {"rank_ic": None, "error": f"仅 {len(valid)} 条"}
    if HAS_SCIPY:
        ric, pval = stats.spearmanr(valid["score"], valid[col])
    else:
        # pandas rank corr 降级
        ric = float(valid["score"].rank().corr(valid[col].rank()))
        pval = None
    return {"rank_ic": round(float(ric), 4), "p_value": round(float(pval), 4) if pval else None, "n": len(valid)}


def calc_rolling_ic(df: pd.DataFrame, horizon: int = 5, window: int = 20) -> list[dict]:
    """滚动 IC 序列 (20日窗口)"""
    col = f"ret_{horizon}d"
    if col not in df.columns:
        return []
    df = df.dropna(subset=[col, "score"]).copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    df = df.sort_values("signal_date").reset_index(drop=True)
    results = []
    for i in range(window, len(df) + 1):
        sub = df.iloc[i - window:i]
        if len(sub) >= 5:
            ic = float(sub["score"].corr(sub[col]))
            results.append({
                "date": df.iloc[i - 1]["signal_date"].strftime("%Y-%m-%d"),
                "ic": round(float(ic), 4),
            })
    return results


def calc_ic_decay(df: pd.DataFrame, horizons: list[int] | None = None) -> dict:
    """IC 衰减曲线: 不同期限下的 IC 变化"""
    if horizons is None:
        horizons = [1, 5, 10, 20]
    decay = {}
    for h in horizons:
        result = calc_ic(df, h)
        decay[f"ret_{h}d"] = result.get("ic")
    return decay


def ic_report() -> dict:
    """完整 IC 报告"""
    df = load_signals()
    if df is None or len(df) < 5:
        return {"error": "信号数据不足"}

    report = {
        "n_signals": len(df),
        "ic_5d": calc_ic(df, 5),
        "rank_ic_5d": calc_rank_ic(df, 5),
        "ic_decay": calc_ic_decay(df),
        "rolling_ic": calc_rolling_ic(df, 5),
    }

    # 打印摘要
    ic5 = report["ic_5d"].get("ic")
    ric5 = report["rank_ic_5d"].get("rank_ic")

    print()
    print("─" * 40)
    print(f"  📊 IC 报告 — {report['n_signals']} 条信号")
    print("─" * 40)
    if ic5 is not None:
        quality = "🟢 有正向预测力" if ic5 > 0.03 else ("🟡 弱预测力" if ic5 > 0 else "🔴 反向预测")
        print(f"  IC(5d): {ic5:+.4f} {quality}")
    if ric5 is not None:
        print(f"  Rank IC(5d): {ric5:+.4f}")
    print("  IC 衰减:", report["ic_decay"])
    print("─" * 40)

    # 保存 JSON
    os.makedirs("output", exist_ok=True)
    with open("output/ic_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    ic_report()
