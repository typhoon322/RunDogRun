"""
report/monitor.py — V3 FINAL 防失效监控系统
==============================================
每7天检查系统健康度, 自动检测是否需要降级。

监控指标 (3 维度):
  1. Score 结构漂移 — mean drift > 10% → WARNING
  2. IC 崩坏 — IC < 0 → DEGRADE RISK
  3. 收益异常 — win_rate sudden drop > 15% → DEGRADE RISK

降级触发条件:
  IF IC < 0 OR win_rate collapse → ACTIVE → WARM_UP

输出监控报告并持久化到 data/monitoring/
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.monitor")

MONITOR_DIR = "data/monitoring"
SIGNALS_CSV = "data/signals/signals_with_returns.csv"


def run_monitoring_check() -> dict:
    """
    执行一次完整监控检查。

    Returns:
        {
            "timestamp": iso,
            "checks": {
                "score_drift": {"status": "OK"/"WARNING"/"DEGRADE", ...},
                "ic_collapse": {"status": "OK"/"WARNING"/"DEGRADE", ...},
                "win_rate": {"status": "OK"/"WARNING"/"DEGRADE", ...},
            },
            "overall": "HEALTHY" / "WARNING" / "DEGRADE",
            "should_degrade": bool,
            "health_score": 0-100,
            "recommendation": str,
        }
    """
    now = datetime.now(CN_TZ)
    result = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "checks": {},
        "overall": "HEALTHY",
        "should_degrade": False,
        "health_score": 100,
        "recommendation": "系统健康, 继续运行",
    }

    # ── Check 1: Score 结构漂移 ──
    result["checks"]["score_drift"] = _check_score_drift()

    # ── Check 2: IC 崩坏 ──
    result["checks"]["ic_collapse"] = _check_ic_collapse()

    # ── Check 3: 收益异常 ──
    result["checks"]["win_rate"] = _check_win_rate()

    # ── 汇总判定 ──
    degrade_checks = []
    warning_checks = []
    health_deduction = 0

    for key, check in result["checks"].items():
        if check.get("status") == "DEGRADE":
            degrade_checks.append(key)
            health_deduction += 35
        elif check.get("status") == "WARNING":
            warning_checks.append(key)
            health_deduction += 15

    result["health_score"] = max(0, 100 - health_deduction)

    if degrade_checks:
        result["should_degrade"] = True
        result["overall"] = "DEGRADE"
        result["recommendation"] = f"触发降级: {', '.join(degrade_checks)}。建议 ACTIVE → WARM_UP"
    elif warning_checks:
        result["overall"] = "WARNING"
        result["recommendation"] = f"警告: {', '.join(warning_checks)}。建议关注, 暂不降级"
    else:
        result["overall"] = "HEALTHY"
        result["recommendation"] = "系统健康, 继续运行"

    # ── 持久化 ──
    _save_result(result)

    return result


def _check_score_drift() -> dict:
    """检查 Score 结构是否漂移"""
    if not os.path.exists(SIGNALS_CSV):
        return {"status": "UNKNOWN", "reason": "无信号数据", "drift": None}

    try:
        df = pd.read_csv(SIGNALS_CSV)
        if "score" not in df.columns or len(df) < 20:
            return {"status": "UNKNOWN", "reason": f"数据不足 ({len(df)} 条)", "drift": None}

        df["signal_date"] = pd.to_datetime(df["signal_date"])
        daily_mean = df.groupby("signal_date")["score"].mean().sort_index()
        scores = daily_mean.values

        if len(scores) < 20:
            return {"status": "UNKNOWN", "reason": f"交易日不足 ({len(scores)})", "drift": None}

        recent_10 = scores[-10:]
        prev_10 = scores[-20:-10]
        mean_recent = float(np.mean(recent_10))
        mean_prev = float(np.mean(prev_10))
        drift = abs(mean_recent - mean_prev) / max(abs(mean_prev), 0.01)

        if drift > 0.10:
            return {
                "status": "WARNING",
                "reason": f"Score 均值漂移 {drift:.1%} > 10%",
                "drift": round(drift, 4),
                "mean_recent": round(mean_recent, 2),
                "mean_prev": round(mean_prev, 2),
            }
        else:
            return {
                "status": "OK",
                "reason": f"Score 结构稳定 (drift={drift:.1%})",
                "drift": round(drift, 4),
                "mean_recent": round(mean_recent, 2),
                "mean_prev": round(mean_prev, 2),
            }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e), "drift": None}


def _check_ic_collapse() -> dict:
    """检查 IC 是否崩坏"""
    try:
        from analytics.ic import load_signals, calc_ic
        df = load_signals()
        if df is None or len(df) < 10:
            return {"status": "UNKNOWN", "reason": "信号数据不足", "ic": None}

        ic_result = calc_ic(df, horizon=5)
        ic_val = ic_result.get("ic")

        if ic_val is None:
            return {"status": "UNKNOWN", "reason": "IC 无法计算", "ic": None}

        if ic_val < 0:
            return {
                "status": "DEGRADE",
                "reason": f"IC(5d)={ic_val:.4f} < 0, 预测方向反转",
                "ic": round(ic_val, 4),
            }
        elif ic_val < 0.02:
            return {
                "status": "WARNING",
                "reason": f"IC(5d)={ic_val:.4f} 偏弱 (< 0.02)",
                "ic": round(ic_val, 4),
            }
        else:
            return {
                "status": "OK",
                "reason": f"IC(5d)={ic_val:.4f} 正常",
                "ic": round(ic_val, 4),
            }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e), "ic": None}


def _check_win_rate() -> dict:
    """检查胜率是否异常下降"""
    if not os.path.exists(SIGNALS_CSV):
        return {"status": "UNKNOWN", "reason": "无信号数据", "drop": None}

    try:
        df = pd.read_csv(SIGNALS_CSV)
        if "ret_5d" not in df.columns or len(df) < 30:
            return {"status": "UNKNOWN", "reason": "数据不足", "drop": None}

        df["signal_date"] = pd.to_datetime(df["signal_date"])
        valid = df.dropna(subset=["ret_5d"])
        if len(valid) < 30:
            return {"status": "UNKNOWN", "reason": "有效数据不足", "drop": None}

        # 按时间排序后分前后两半计算胜率
        valid = valid.sort_values("signal_date")
        half = len(valid) // 2
        recent = valid.iloc[half:]
        prev = valid.iloc[:half]

        wr_recent = (recent["ret_5d"] > 0).sum() / len(recent)
        wr_prev = (prev["ret_5d"] > 0).sum() / len(prev)
        drop = wr_prev - wr_recent

        if drop > 0.15:
            return {
                "status": "DEGRADE",
                "reason": f"胜率突降 {drop:.0%} ({wr_prev:.0%}→{wr_recent:.0%})",
                "drop": round(drop, 4),
                "win_rate_recent": round(wr_recent, 4),
                "win_rate_prev": round(wr_prev, 4),
            }
        elif drop > 0.05:
            return {
                "status": "WARNING",
                "reason": f"胜率下降 {drop:.0%} ({wr_prev:.0%}→{wr_recent:.0%})",
                "drop": round(drop, 4),
                "win_rate_recent": round(wr_recent, 4),
                "win_rate_prev": round(wr_prev, 4),
            }
        else:
            return {
                "status": "OK",
                "reason": f"胜率稳定 ({wr_recent:.0%})",
                "drop": round(drop, 4),
                "win_rate_recent": round(wr_recent, 4),
                "win_rate_prev": round(wr_prev, 4),
            }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e), "drop": None}


def _save_result(result: dict):
    """持久化监控结果"""
    os.makedirs(MONITOR_DIR, exist_ok=True)
    date_str = result.get("date", datetime.now(CN_TZ).strftime("%Y-%m-%d"))
    path = os.path.join(MONITOR_DIR, f"monitor_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"监控报告已保存: {path}")


def load_monitor_history(n: int = 5) -> list[dict]:
    """加载最近 n 次监控结果"""
    if not os.path.exists(MONITOR_DIR):
        return []
    files = sorted([f for f in os.listdir(MONITOR_DIR) if f.endswith(".json")], reverse=True)
    results = []
    for f in files[:n]:
        with open(os.path.join(MONITOR_DIR, f), encoding="utf-8") as fp:
            results.append(json.load(fp))
    return results


def print_monitor(result: dict):
    """控制台输出监控结果"""
    print()
    print("─" * 50)
    overall_icon = {"HEALTHY": "✅", "WARNING": "⚠️", "DEGRADE": "🚨"}
    icon = overall_icon.get(result["overall"], "❓")
    print(f"  {icon} 监控检查 — {result['overall']} (health={result['health_score']})")
    print("─" * 50)
    for key, check in result.get("checks", {}).items():
        status = check.get("status", "?")
        s_icon = {"OK": "✅", "WARNING": "⚠️", "DEGRADE": "🚨", "UNKNOWN": "❓", "ERROR": "❌"}.get(status, "?")
        print(f"  {s_icon} {key}: {check.get('reason', '')}")
    print(f"  💡 建议: {result.get('recommendation', '')}")
    print("─" * 50)


if __name__ == "__main__":
    result = run_monitoring_check()
    print_monitor(result)
