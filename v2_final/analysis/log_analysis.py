"""
v2_final/analysis/log_analysis.py — v2.1 性能分析
====================================================
从 trade_log.jsonl 读取历史, 计算胜率/置信度/频率
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("v2.analysis")

TRADE_LOG = "logs/trade_log.jsonl"


def analyze_logs(path: str = TRADE_LOG) -> dict[str, Any]:
    """分析交易日志"""
    fp = Path(path)
    if not fp.exists():
        return {"total_trades": 0, "win_rate": 0.5, "avg_confidence": 0.6}

    trades = []
    try:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return {"total_trades": 0, "win_rate": 0.5, "avg_confidence": 0.6}

    if not trades:
        return {"total_trades": 0, "win_rate": 0.5, "avg_confidence": 0.6}

    # 只统计执行结果
    exec_trades = [t for t in trades if t.get("type") == "execution"]
    signal_trades = [t for t in trades if t.get("type") == "signal"]

    win_count = sum(1 for t in exec_trades if t.get("status") == "filled")
    total = len(exec_trades) or 1
    win_rate = round(win_count / total, 3)

    # 平均置信度
    confs = [t.get("confidence", 0.6) for t in signal_trades]
    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.6

    # 最近7天交易频率
    from datetime import datetime, timedelta
    recent = []
    cutoff = datetime.now() - timedelta(days=7)
    for t in trades:
        try:
            d = datetime.fromisoformat(t.get("date", ""))
            if d > cutoff:
                recent.append(t)
        except (ValueError, TypeError):
            pass

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "avg_confidence": avg_conf,
        "recent_trades": len(recent),
        "signal_count": len(signal_trades),
        "trade_frequency": round(len(recent) / 7, 1),  # 日均
    }
