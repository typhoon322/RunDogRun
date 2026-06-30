"""
stats/stability.py — V3 FINAL Score 稳定性计算
=================================================
判断系统评分是否达到统计收敛。

核心指标:
  - mean_drift: 近10日均值 vs 前10日均值的相对漂移
  - std_drift:  近10日标准差 vs 前10日标准差的相对漂移
  - stable:     mean_drift < 5% AND std_drift < 10%

数据来源:
  - daily_report.json 中的 system_score / avg_score
  - 或直接传入 score 序列
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

logger = logging.getLogger("v3.stability")

CN_TZ = timezone(timedelta(hours=8))

# 历史日报目录
REPORT_DIR = Path("output")
DAILY_REPORT = "output/daily_report.json"

# 备用: 从 pipeline_log.json 提取
PIPELINE_LOG = "output/pipeline_log.json"


def load_score_history() -> list[float]:
    """
    从历史日报中提取 score 序列。

    优先从 daily_report.json 的历史记录中提取 avg_score / system_score。
    如果没有历史, 返回空列表。
    """
    scores = []

    # 方案1: 从 signal 日志提取每日 mean score
    signal_log = "logs/signals.jsonl"
    if os.path.exists(signal_log):
        import pandas as pd
        try:
            signals = []
            with open(signal_log, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            signals.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            if signals:
                df = pd.DataFrame(signals)
                df["signal_date"] = pd.to_datetime(df["signal_date"])
                daily_mean = df.groupby("signal_date")["score"].mean().sort_index()
                scores = [float(s) for s in daily_mean.values]
                logger.info(f"从信号日志提取 {len(scores)} 天 score 历史")
        except Exception as e:
            logger.warning(f"信号日志读取失败: {e}")

    return scores


def compute_stability(scores: list[float] | None = None) -> dict:
    """
    计算 Score 稳定性。

    Args:
        scores: score 序列 (每日一个值)。如果为 None, 自动从历史加载。

    Returns:
        {
            "n": 样本数,
            "mean_recent": 近10日均值,
            "mean_prev": 前10日均值,
            "std_recent": 近10日标准差,
            "std_prev": 前10日标准差,
            "mean_drift": 均值相对漂移率,
            "std_drift": 标准差相对漂移率,
            "stable": bool,
            "reason": str,
        }
    """
    if scores is None:
        scores = load_score_history()

    result = {
        "n": len(scores),
        "mean_recent": None,
        "mean_prev": None,
        "std_recent": None,
        "std_prev": None,
        "mean_drift": None,
        "std_drift": None,
        "stable": False,
        "reason": "",
    }

    if len(scores) < 20:
        result["reason"] = f"数据不足: {len(scores)}/20 天"
        return result

    recent_10 = scores[-10:]
    prev_10 = scores[-20:-10]

    mean_recent = float(np.mean(recent_10))
    mean_prev = float(np.mean(prev_10))
    std_recent = float(np.std(recent_10))
    std_prev = float(np.std(prev_10))

    # 相对漂移率
    mean_drift = abs(mean_recent - mean_prev) / max(abs(mean_prev), 0.01)
    std_drift = abs(std_recent - std_prev) / max(std_prev, 0.01) if std_prev > 0 else 0

    result.update({
        "mean_recent": round(mean_recent, 2),
        "mean_prev": round(mean_prev, 2),
        "std_recent": round(std_recent, 2),
        "std_prev": round(std_prev, 2),
        "mean_drift": round(mean_drift, 4),
        "std_drift": round(std_drift, 4),
    })

    # 稳定性判定
    mean_ok = mean_drift < 0.05
    std_ok = std_drift < 0.10

    if mean_ok and std_ok:
        result["stable"] = True
        result["reason"] = f"稳定 (mean_drift={mean_drift:.1%}, std_drift={std_drift:.1%})"
    else:
        reasons = []
        if not mean_ok:
            reasons.append(f"均值漂移 {mean_drift:.1%} >= 5%")
        if not std_ok:
            reasons.append(f"标准差漂移 {std_drift:.1%} >= 10%")
        result["reason"] = ", ".join(reasons)

    return result


def stability_report() -> dict:
    """生成稳定性报告并打印"""
    report = compute_stability()

    print()
    print("─" * 50)
    print(f"  📊 Score 稳定性报告 — {report['n']} 天样本")
    print("─" * 50)

    if report["stable"]:
        print(f"  ✅ 稳定: {report['reason']}")
    else:
        print(f"  ⏳ 未稳定: {report['reason']}")

    if report["mean_recent"] is not None:
        print(f"  近10日: mean={report['mean_recent']:.1f} std={report['std_recent']:.1f}")
        print(f"  前10日: mean={report['mean_prev']:.1f} std={report['std_prev']:.1f}")
        print(f"  漂移:   mean={report['mean_drift']:.1%} std={report['std_drift']:.1%}")

    print("─" * 50)

    # 保存
    os.makedirs("output", exist_ok=True)
    with open("output/stability_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    stability_report()
