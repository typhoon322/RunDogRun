"""
v2_final/utils/equity_tracker.py — v2.5 净值追踪
====================================================
净值曲线 + 回撤曲线 + 保存/加载
"""
import json
from pathlib import Path
from typing import Any


class EquityTracker:
    """净值 + 回撤 双曲线追踪"""

    def __init__(self):
        self.curve: list[float] = []
        self._peak = 0.0

    def update(self, value: float) -> None:
        self.curve.append(round(value, 4))
        if value > self._peak:
            self._peak = value

    def drawdown_curve(self) -> list[float]:
        """回撤曲线 (百分比)"""
        if not self.curve:
            return []
        peak = self.curve[0]
        dd = []
        for v in self.curve:
            if v > peak:
                peak = v
            dd.append(round((peak - v) / peak * 100, 2) if peak > 0 else 0.0)
        return dd

    def current_drawdown(self) -> float:
        dd = self.drawdown_curve()
        return dd[-1] if dd else 0.0

    def summary(self) -> dict[str, Any]:
        n = len(self.curve)
        if n < 2:
            return {"total_return": 0, "max_drawdown": 0, "n_days": n}

        total_ret = round((self.curve[-1] / self.curve[0] - 1) * 100, 2)
        dd = self.drawdown_curve()
        max_dd = max(dd) if dd else 0
        cur_dd = dd[-1] if dd else 0

        return {
            "total_return_pct": total_ret,
            "max_drawdown_pct": max_dd,
            "current_drawdown_pct": cur_dd,
            "n_days": n,
            "latest_value": self.curve[-1] if self.curve else 1.0,
        }

    def save(self, path: str = "state/equity.json") -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "curve": self.curve,
            "drawdown": self.drawdown_curve(),
            "summary": self.summary(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load(self, path: str = "state/equity.json") -> bool:
        fp = Path(path)
        if not fp.exists():
            return False
        try:
            with open(fp) as f:
                data = json.load(f)
            self.curve = data.get("curve", [])
            self._peak = max(self.curve) if self.curve else 0.0
            return True
        except (json.JSONDecodeError, OSError):
            return False
