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


class Result:
    """标准化输出结果包装器 — 可 save() + summary()"""
    def __init__(self, data: dict):
        self.data = data

    def save(self, path: str = "data/outputs/latest.json") -> str:
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        return path

    def summary(self) -> dict:
        d = self.data
        return {
            "date": d.get("date", ""),
            "v5_regime": d.get("market_regime", d.get("v5_regime", "unknown")),
            "v6_resonance": d.get("resonance", {}).get("label", d.get("v6_resonance", "flat")),
            "strategy_mode": d.get("strategy_mode", "unknown"),
            "data_quality": d.get("data_quality", "ok"),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return f"Result(date={s['date']}, regime={s['v5_regime']}, resonance={s['v6_resonance']}, quality={s['data_quality']})"
