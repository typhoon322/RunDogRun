"""
context.py — 系统上下文 (状态文件读写 + 历史管理)
"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.engine.context")


STATE_DIR = "state"
STATE_FILE = f"{STATE_DIR}/system_state.json"


def load_state() -> dict[str, Any]:
    """加载系统状态文件"""
    fp = Path(STATE_FILE)
    if fp.exists():
        try:
            with open(fp, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def save_state(state: dict[str, Any]) -> None:
    """持久化系统状态"""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _default_state() -> dict[str, Any]:
    return {
        "last_run": None,
        "market_regime": "unknown",
        "resonance": "flat",
        "current_exposure": 0.0,
        "signal_history": [],
        "total_runs": 0,
    }


class Context:
    """系统运行上下文"""

    def __init__(self, date_str: str, data_dir: str = "data"):
        self.date_str = date_str
        self.data_dir = data_dir
        self.state = load_state()
        self.state["last_run"] = date_str
        self.state["total_runs"] += 1

    def update_regime(self, regime: str, score: float = 0):
        self.state["market_regime"] = regime
        self.state["regime_score"] = score

    def update_resonance(self, label: str, score: float = 0):
        self.state["resonance"] = label
        self.state["resonance_score"] = score

    def update_exposure(self, exposure: float):
        self.state["current_exposure"] = exposure

    def record_signal(self, signal: dict):
        self.state.setdefault("signal_history", []).append(signal)
        # 保留最近100条
        self.state["signal_history"] = self.state["signal_history"][-100:]

    def flush(self):
        save_state(self.state)
        logger.info("状态已持久化")
