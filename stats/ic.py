"""
stats/ic.py — V3 FINAL IC 模块 (re-export from analytics)
============================================================
统一入口: stats.ic → analytics.ic
"""
# Re-export 所有公共接口
from analytics.ic import (
    load_signals,
    calc_ic,
    calc_rank_ic,
    calc_rolling_ic,
    calc_ic_decay,
    ic_report,
)

__all__ = [
    "load_signals",
    "calc_ic",
    "calc_rank_ic",
    "calc_rolling_ic",
    "calc_ic_decay",
    "ic_report",
]
