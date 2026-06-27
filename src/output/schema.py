"""
schema.py — 输出 JSON Schema 定义
===================================
标准化所有输出层的数据结构
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["date", "version", "v5_regime", "v6_resonance", "data_quality"],
    "properties": {
        "date": {"type": "string"},
        "version": {"type": "string"},
        "v5_regime": {"enum": ["trend_market", "range_market", "downtrend_market", "crash_market"]},
        "v6_resonance": {"enum": ["strong_alignment", "moderate", "weak", "conflict"]},
        "data_quality": {"enum": ["ok", "warning", "failed"]},
        "sectors": {"type": "array"},
        "leaders": {"type": "array"},
        "signals": {"type": "array"},
        "risk": {"type": "object"},
        "weights": {"type": "object"},
        "rl_agent": {"type": "object"},
        "backtest": {"type": "object"},
    },
}

LEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "name": {"type": "string"},
        "sector": {"type": "string"},
        "life_cycle_stage": {"type": "string"},
        "leader_score": {"type": "number"},
        "position_size": {"type": "number"},
    },
}

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "action": {"enum": ["BUY", "SELL", "HOLD", "EMPTY", "NO_ACTION"]},
        "signal_type": {"type": "string"},
        "signal_grade": {"enum": ["A+", "A", "B", "C", "D", "E", "F"]},
        "confidence": {"type": "number"},
        "position_size": {"type": "number"},
    },
}
