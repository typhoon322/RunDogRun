"""
v2_final/core/pipeline_logger.py — 管道状态追踪器
=====================================================
每一步必须记录: step / status / detail / time
输出: data/outputs/pipeline_log.json
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

CN_TZ = timezone(timedelta(hours=8))


class PipelineLogger:
    """全链路状态追踪 — 白盒可观测"""

    def __init__(self):
        self.steps: list[dict[str, Any]] = []
        self._log("pipeline_init", "ok", "v2.5 pipeline started")

    def _log(self, step: str, status: str, detail: str = "") -> None:
        self.steps.append({
            "step": step,
            "status": status,
            "detail": str(detail),
            "time": datetime.now(CN_TZ).strftime("%H:%M:%S"),
        })

    def ok(self, step: str, detail: str = "") -> None:
        self._log(step, "ok", detail)

    def fail(self, step: str, error: str) -> None:
        self._log(step, "fail", error)

    def skip(self, step: str, reason: str) -> None:
        self._log(step, "skip", reason)

    def save(self, path: str = "data/outputs/pipeline_log.json") -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"steps": self.steps, "total": len(self.steps),
                        "ok_count": sum(1 for s in self.steps if s["status"] == "ok"),
                        "fail_count": sum(1 for s in self.steps if s["status"] == "fail")},
                       f, ensure_ascii=False, indent=2)
        return path

    def summary(self) -> dict:
        return {
            "total": len(self.steps),
            "ok": sum(1 for s in self.steps if s["status"] == "ok"),
            "fail": sum(1 for s in self.steps if s["status"] == "fail"),
            "skip": sum(1 for s in self.steps if s["status"] == "skip"),
            "last_step": self.steps[-1]["step"] if self.steps else "none",
        }
