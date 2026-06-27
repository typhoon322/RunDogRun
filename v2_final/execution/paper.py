"""
v2_final/execution/paper.py — 模拟执行
========================================
记录交易信号, 模拟成交
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("v2.execution")

TRADE_LOG = "logs/trades.jsonl"


def execute(signal: dict, portfolio: dict) -> dict[str, Any]:
    """模拟执行交易信号"""
    action = signal.get("action", "HOLD")
    if action != "BUY":
        return {"status": "hold", "action": action}

    result = {
        "date": datetime.now().isoformat(),
        "status": "filled",
        "action": action,
        "stock": signal.get("stock_code", ""),
        "name": signal.get("stock_name", ""),
        "confidence": signal.get("confidence", 0),
        "position_size": signal.get("position_size", 0.10),
        "mode": "paper",
    }

    # 记录日志
    _log_trade(result)
    logger.info(f"模拟成交: {result['stock']} {result['name']}")

    return result


def _log_trade(result: dict) -> None:
    Path("logs").mkdir(exist_ok=True)
    with open(TRADE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
