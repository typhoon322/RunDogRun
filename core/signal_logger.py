"""
core/signal_logger.py — v3.0 信号记录器
=============================================
JSONL 追加写入 logs/signals.jsonl, 崩溃安全
从 daily_report.json 提取每日信号, 支持回读历史
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))

logger = logging.getLogger("v3.signal")

SIGNAL_LOG = "logs/signals.jsonl"


def log_signals(portfolio: list[dict], market_state: str = ""):
    """
    将当日选股结果追加写入信号日志。

    Args:
        portfolio: [{"code":"601016","name":"节能风电","price":3.94,"score":10.24,"weight":0.233}, ...]
        market_state: "OK_TRADE" / "NO_TRADE" / "CAUTION"
    """
    if not portfolio:
        return

    signal_date = datetime.now(CN_TZ).strftime("%Y-%m-%d")
    now_iso = datetime.now(CN_TZ).isoformat()

    os.makedirs(os.path.dirname(SIGNAL_LOG), exist_ok=True)

    count = 0
    with open(SIGNAL_LOG, "a", encoding="utf-8") as f:
        for p in portfolio:
            signal = {
                "signal_date": signal_date,
                "stock_code": str(p.get("code", "")).zfill(6),
                "stock_name": p.get("name", ""),
                "entry_close": p.get("price", 0),
                "score": p.get("score", 0),
                "weight": p.get("weight", 0),
                "market_state": market_state,
                "recorded_at": now_iso,
            }
            f.write(json.dumps(signal, ensure_ascii=False) + "\n")
            count += 1

    logger.info(f"信号已记录: {count} 条 → {SIGNAL_LOG}")


def load_history() -> list[dict]:
    """读取全部信号历史"""
    if not os.path.exists(SIGNAL_LOG):
        return []
    signals = []
    with open(SIGNAL_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return signals


def stats() -> dict:
    """信号统计"""
    signals = load_history()
    if not signals:
        return {"total": 0, "date_range": "", "unique_stocks": 0}
    dates = sorted(set(s["signal_date"] for s in signals))
    codes = set(s["stock_code"] for s in signals)
    return {
        "total": len(signals),
        "date_range": f"{dates[0]} ~ {dates[-1]}" if dates else "",
        "unique_stocks": len(codes),
    }
