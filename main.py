"""
main.py — v6 量化系统入口
============================
默认运行完整管道 (v1→v6)
兼容旧接口: --analyze, --trade, --cycle, --execute, --regime
"""

import json
import os
import sys

import config
from src.utils import setup_logging, is_trading_day

logger = setup_logging()


def run_pipeline(date_str: str) -> int:
    """运行完整 v1-v6 管道"""
    from src.engine.pipeline import run
    output = run(date_str)
    quality = output.get("data_quality", "ok")
    if quality == "failed":
        return 2
    elif quality == "warning":
        return 1
    return 0


def run_single_step(date_str: str, step: str) -> int:
    """运行单个分析步骤 (向后兼容)"""
    data_path = f"{config.DATA_DIR}/{date_str}.json"
    if not os.path.exists(data_path) and step not in ("collect",):
        logger.error(f"数据不存在: {data_path}")
        return 2

    if step == "analyze":
        from src.v2_sector.sector_score import score_sectors
        from src.v1_2_stock.stock_score import score_stocks
        from src.engine.analyzer import analyze as _analyze
        result = _analyze(date_str)
    elif step == "trade":
        from src.v1_4_risk.risk_control import trade
        result = trade(date_str)
    elif step == "cycle":
        from src.v2_sector.sector_cycle import analyze_cycle
        result = analyze_cycle(date_str)
    elif step == "execute":
        from src.v5_regime.trade_executor import execute
        result = execute(date_str)
    elif step == "regime":
        from src.v5_regime.market_regime import analyze_regime
        result = analyze_regime(date_str)
    else:
        logger.error(f"未知步骤: {step}")
        return 2

    out_path = f"{config.DATA_DIR}/{date_str}_{step}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"输出: {out_path}")
    return 0


def main() -> int:
    date_str = config.today_cn()
    mode = "pipeline"  # 默认跑全管道
    check_only = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--check-only":
            check_only = True
            i += 1
        elif args[i] in ("--analyze", "--trade", "--cycle", "--execute", "--regime"):
            mode = args[i][2:]
            i += 1
        elif args[i] == "--help":
            print("v6 量化系统")
            print("  python main.py                    # 完整管道 v1→v6")
            print("  python main.py --date YYYY-MM-DD   # 指定日期")
            print("  python main.py --check-only        # 交易日检查")
            print("  python main.py --analyze/--trade/--cycle/--execute/--regime")
            return 0
        else:
            i += 1

    # 交易日检查 (非分析模式)
    if mode == "pipeline" and not check_only:
        if not is_trading_day(date_str):
            logger.info(f"{date_str} 非交易日, 跳过")
            return 0

    if check_only:
        logger.info(f"{date_str} {'是' if is_trading_day(date_str) else '非'}交易日")
        return 0

    # 执行
    if mode == "pipeline":
        return run_pipeline(date_str)
    else:
        return run_single_step(date_str, mode)


if __name__ == "__main__":
    sys.exit(main())
