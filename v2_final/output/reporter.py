"""
v2_final/output/reporter.py — 输出报告
=========================================
生成标准化 JSON 信号文件
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def build_report(
    signal: dict, sector_rank: list, leaders: list,
    execution_result: dict, risk_ok: bool,
) -> dict[str, Any]:
    """构建最终输出"""
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "signal": signal,
        "top_sectors": [{"name": s["name"], "strength": s["strength"], "level": s["level"]}
                        for s in sector_rank[:5]],
        "top_leaders": leaders[:5],
        "risk_check": "pass" if risk_ok else "blocked",
        "execution": execution_result,
    }


def save_report(report: dict, path: str = "data/outputs/v2_latest.json") -> str:
    """保存报告"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path
