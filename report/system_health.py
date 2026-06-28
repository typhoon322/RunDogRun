"""
report/system_health.py — v2.8 系统健康评分 (封版)
==========================================================
每天给系统本身打分: 数据完整 + Pipeline执行 + 回测产出 + 收益稳定

Returns:
    {score: 0-100, level: "🟢稳定/🟡一般/🔴异常",
     checks: {...}, verdict: "今天值不值得看"}
"""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("system.health")

OUTPUT_DIR = "output"


def _read_json(filename: str) -> dict | None:
    for d in [OUTPUT_DIR, "data/outputs"]:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None


def system_health_score() -> dict:
    """
    系统多维健康评分 (0-100)。

    评分维度:
      - 数据完整性 (25分): CSV数量、Registry状态
      - Pipeline执行 (25分): 日志是否存在, 失败步骤数
      - 回测产出 (25分): equity_curve 是否存在, 长度是否够
      - 收益稳定性 (25分): 近期波动是否在合理范围
    """
    score = 100
    checks = {}

    today = datetime.now().strftime("%Y-%m-%d")

    # ═══════════════════════════════════════════
    # 1. 数据完整性 (25分)
    # ═══════════════════════════════════════════
    data_dir = "data/raw/daily"
    csv_count = len(os.listdir(data_dir)) if os.path.exists(data_dir) else 0

    if csv_count >= 300:
        checks["data"] = {"ok": True, "score": 25, "detail": f"{csv_count} CSV, 充足"}
    elif csv_count >= 100:
        penalty = max(0, (300 - csv_count) // 10)
        checks["data"] = {"ok": True, "score": max(15, 25 - penalty),
                         "detail": f"{csv_count} CSV, 偏低"}
        score -= penalty
    elif csv_count > 0:
        checks["data"] = {"ok": False, "score": 5, "detail": f"仅{csv_count} CSV, 严重不足"}
        score -= 20
    else:
        checks["data"] = {"ok": False, "score": 0, "detail": "无CSV数据"}
        score -= 25

    # ═══════════════════════════════════════════
    # 2. Pipeline 执行 (25分)
    # ═══════════════════════════════════════════
    plog = _read_json("pipeline_log.json")
    if plog:
        fail_count = plog.get("fail_count", 0)
        total = plog.get("total", 0)
        if fail_count == 0:
            checks["pipeline"] = {"ok": True, "score": 25,
                                 "detail": f"{total}步全通过"}
        else:
            penalty = min(20, fail_count * 5)
            checks["pipeline"] = {"ok": False, "score": max(5, 25 - penalty),
                                 "detail": f"{fail_count}/{total} 失败"}
            score -= penalty
    else:
        checks["pipeline"] = {"ok": False, "score": 0, "detail": "日志缺失"}
        score -= 25

    # ═══════════════════════════════════════════
    # 3. 回测产出 (25分)
    # ═══════════════════════════════════════════
    equity = _read_json("equity_curve.json")
    if equity:
        curve = equity.get("curve", [])
        if len(curve) >= 50:
            checks["backtest"] = {"ok": True, "score": 25,
                                 "detail": f"{len(curve)}天曲线, 充足"}
        elif len(curve) >= 10:
            checks["backtest"] = {"ok": True, "score": 15,
                                 "detail": f"仅{len(curve)}天, 偏低"}
            score -= 10
        else:
            checks["backtest"] = {"ok": False, "score": 5,
                                 "detail": f"仅{len(curve)}天, 严重不足"}
            score -= 20
    else:
        checks["backtest"] = {"ok": False, "score": 0, "detail": "无回测数据"}
        score -= 25

    # ═══════════════════════════════════════════
    # 4. 收益稳定性 (25分)
    # ═══════════════════════════════════════════
    if equity and equity.get("curve") and len(equity["curve"]) >= 5:
        curve = equity["curve"]
        recent_return = curve[-1] / curve[-5] - 1 if len(curve) >= 5 else 0

        if abs(recent_return) < 0.05:
            checks["stability"] = {"ok": True, "score": 25,
                                  "detail": f"近5日波动 {recent_return:+.2%}, 正常"}
        elif abs(recent_return) < 0.10:
            checks["stability"] = {"ok": True, "score": 15,
                                  "detail": f"近5日波动 {recent_return:+.2%}, 偏高"}
            score -= 10
        else:
            checks["stability"] = {"ok": False, "score": 5,
                                  "detail": f"近5日波动 {recent_return:+.2%}, 剧烈"}
            score -= 20
    else:
        checks["stability"] = {"ok": False, "score": 0, "detail": "数据不足"}
        score -= 25

    # ═══════════════════════════════════════════
    # 综合判定
    # ═══════════════════════════════════════════
    score = max(0, min(100, score))

    if score >= 85:
        level = "🟢 稳定"
        verdict = "系统运行正常，可以正常参考结果"
    elif score >= 60:
        level = "🟡 一般"
        verdict = "系统有部分异常，建议谨慎参考"
    else:
        level = "🔴 异常"
        verdict = "系统严重异常，建议暂停参考，等待修复"

    result = {
        "score": score,
        "level": level,
        "verdict": verdict,
        "checks": checks,
        "date": today,
    }

    # 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs("data/outputs", exist_ok=True)
    for d in [OUTPUT_DIR, "data/outputs"]:
        path = os.path.join(d, "system_health.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def print_health(result: dict):
    """控制台输出"""
    checks = result.get("checks", {})
    print()
    print("─" * 40)
    print(f"  🧠 系统健康: {result['score']}/100 {result['level']}")
    print("─" * 40)
    for name, c in checks.items():
        icon = "✅" if c["ok"] else "❌"
        label = {"data": "数据", "pipeline": "Pipeline", "backtest": "回测", "stability": "稳定"}
        print(f"  {icon} {label.get(name, name)}: {c['detail']} ({c['score']}分)")
    print(f"\n  👉 {result['verdict']}")
    print("─" * 40)


if __name__ == "__main__":
    print_health(system_health_score())
