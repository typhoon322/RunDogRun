"""
experience.py — v11 经验回放池
=================================
存储每笔交易结果, 用于策略回顾和学习
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v11.experience")


class ExperienceBuffer:
    """交易经验池 — FIFO, 保留最近N条"""

    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.memory: list[dict[str, Any]] = []

    def add(self, trade: dict[str, Any]) -> None:
        self.memory.append(trade)
        if len(self.memory) > self.capacity:
            self.memory = self.memory[-self.capacity:]

    def sample(self, n: int = 100) -> list[dict[str, Any]]:
        return self.memory[-n:]

    def recent_stats(self, window: int = 20) -> dict[str, Any]:
        recent = self.memory[-window:]
        if not recent:
            return {"trades": 0}

        wins = sum(1 for t in recent if t.get("pnl_pct", 0) > 0)
        pnls = [t.get("pnl_pct", 0) for t in recent]
        avg_pnl = sum(pnls) / len(pnls)

        return {
            "trades": len(recent),
            "win_rate": round(wins / len(recent), 2),
            "avg_pnl_pct": round(avg_pnl, 2),
            "total_pnl": round(sum(pnls), 2),
            "max_win": round(max(pnls), 2),
            "max_loss": round(min(pnls), 2),
        }

    def save(self, path: str = "state/v11_experience.json") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.memory[-200:], f, ensure_ascii=False, indent=2)

    def load(self, path: str = "state/v11_experience.json") -> bool:
        fp = Path(path)
        if not fp.exists():
            return False
        try:
            with open(fp) as f:
                self.memory = json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False
