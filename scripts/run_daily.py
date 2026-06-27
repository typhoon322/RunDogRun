#!/usr/bin/env python3
"""
每日运行脚本 — 完整 v1→v8 管道执行
用法: python scripts/run_daily.py [--date YYYY-MM-DD]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import get_logger
from src.engine.pipeline import run as run_pipeline

logger = get_logger("daily-run")

if __name__ == "__main__":
    import config
    date_str = config.today_cn()

    if len(sys.argv) >= 3 and sys.argv[1] == "--date":
        date_str = sys.argv[2]

    logger.info(f"Daily run: {date_str}")
    output = run_pipeline(date_str)
    logger.info(f"Done: quality={output.get('data_quality', '?')}")
