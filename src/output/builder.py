"""
builder.py — 输出构建器
=========================
将 pipeline 各层结果组装为标准化 JSON
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import config


def build_output(date_str: str, layers: dict[str, Any]) -> dict[str, Any]:
    """组装最终输出 JSON"""
    output = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "8.0.0",

        # v5 市场状态
        "v5_regime": layers.get("regime", {}).get("market_regime", "unknown"),
        "v6_resonance": layers.get("resonance", {}).get("overall", {}).get("label", "flat"),

        # v2 板块
        "sectors": layers.get("sectors", [])[:10],

        # v3 龙头
        "leaders": layers.get("leaders", [])[:5],

        # v1 信号
        "signals": layers.get("signals", [])[:10],

        # v4 风控
        "risk": layers.get("risk", {}),

        # v6 自适应权重
        "weights": layers.get("weights", {}),

        # v8 RL Agent
        "rl_agent": layers.get("rl_agent", {}),

        # v7 回测 (如触发)
        "backtest": layers.get("backtest", {}),

        # 数据质量
        "data_quality": layers.get("quality", "ok"),
    }
    return output


def save_output(output: dict, date_str: str, data_dir: str = "data/outputs") -> str:
    """保存主输出文件"""
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    path = Path(data_dir) / f"{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return str(path)


def save_latest(output: dict, data_dir: str = "data/outputs") -> str:
    """保存 latest.json"""
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    path = Path(data_dir) / "latest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return str(path)
