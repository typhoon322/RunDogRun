"""
v2_final/utils/logger.py — v2.1 结构化交易日志
=================================================
JSONL 格式, 每笔交易一行
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


TRADE_LOG = "logs/trade_log.jsonl"


def log_trade(data: dict[str, Any]) -> None:
    """记录一笔交易到 JSONL 日志"""
    os.makedirs("logs", exist_ok=True)
    data["date"] = datetime.now().isoformat()
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def log_signal(signal: dict[str, Any]) -> None:
    """记录信号 (含置信度和原因)"""
    log_trade({
        "type": "signal",
        "action": signal.get("action", "HOLD"),
        "stock": signal.get("stock_code", ""),
        "confidence": signal.get("confidence", 0),
        "reason": signal.get("reason", ""),
    })


def log_execution(result: dict[str, Any]) -> None:
    """记录执行结果"""
    log_trade({
        "type": "execution",
        "status": result.get("status", ""),
        "stock": result.get("stock", ""),
        "mode": result.get("mode", "paper"),
    })
