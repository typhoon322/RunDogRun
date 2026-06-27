"""
v2_final/report/daily_report.py — 日报生成器
================================================
输出标准化 JSON 日报 + CLI 友好摘要
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("v2.report")


def generate_report(
    symbol: str,
    signal: dict[str, Any],
    backtest_result: dict[str, Any],
    live_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成完整日报"""

    bt = backtest_result.get("metrics", {})

    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "version": "2.2.0",
        "symbol": symbol,

        # 当日信号
        "live_signal": live_signal or signal,

        # 回测绩效
        "backtest": {
            "total_return_pct": bt.get("total_return_pct", 0),
            "annual_return_pct": bt.get("annual_return_pct", 0),
            "max_drawdown_pct": bt.get("max_drawdown_pct", 0),
            "win_rate": bt.get("win_rate", 0),
            "avg_win_pct": bt.get("avg_win_pct", 0),
            "avg_loss_pct": bt.get("avg_loss_pct", 0),
            "total_trades": backtest_result.get("total_trades", 0),
        },

        # 策略评级
        "strategy_health": _health_check(bt),
    }

    return report


def save_report(report: dict, path: str = "data/outputs/daily_report.json") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def print_summary(report: dict) -> None:
    """控制台友好摘要"""
    bt = report.get("backtest", {})
    print()
    print("═" * 40)
    print(f"  📊 日报 {report['date']} — {report['symbol']}")
    print(f"  📈 回测收益: {bt.get('total_return_pct', 0):+.1f}%")
    print(f"  📉 最大回撤: {bt.get('max_drawdown_pct', 0):.1f}%")
    print(f"  🎯 胜率: {bt.get('win_rate', 0):.0%}")
    print(f"  🧠 策略状态: {report.get('strategy_health', 'unknown')}")
    sig = report.get("live_signal", {})
    print(f"  📡 今日信号: {sig.get('action', '?')} conf={sig.get('confidence', 0):.0%}")
    print("═" * 40)


def _health_check(bt: dict) -> str:
    """策略健康检查"""
    ret = bt.get("total_return_pct", 0)
    dd = abs(bt.get("max_drawdown_pct", 99))
    wr = bt.get("win_rate", 0)

    if ret > 10 and dd < 15 and wr > 0.5:
        return "HEALTHY ✅"
    elif ret > 0 and dd < 20:
        return "OK ⚠️"
    elif dd > 25:
        return "RISKY 🔴"
    return "UNKNOWN"
