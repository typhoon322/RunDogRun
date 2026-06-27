#!/usr/bin/env python3
"""回测运行脚本"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.logger import get_logger
from src.v7.backtest_engine import run_backtest
logger = get_logger("backtest")
date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-06-26"
logger.info(f"Backtest: {date_str}")
bt = run_backtest("2026-01-01", date_str)
m = bt.get("metrics", {})
logger.info(f"Score={m.get('strategy_score')}, Return={m.get('total_return_pct')}%")
