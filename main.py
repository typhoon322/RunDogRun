"""
main.py — v2.0 极简实盘系统
=============================
闭环: 数据 → 板块 → 选股 → 风控 → 信号 → 执行 → 记录

用法: python main.py
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v2")


def run():
    logger.info("v2.0 启动")

    # 1. 数据
    from v2_final.data.provider import get_market_data
    data = get_market_data()
    if not data["stocks"]:
        logger.warning("数据为空, 退出")
        return

    # 2. 板块强度
    from v2_final.strategy.sector import calc_sector_strength
    sector_rank = calc_sector_strength(data["sectors"])
    logger.info(f"板块: {sector_rank[0]['name']} {sector_rank[0]['strength']:.1f}")

    # 3. 选股
    from v2_final.strategy.stock import pick_leaders
    leaders = pick_leaders(data["stocks"])
    logger.info(f"龙头: {len(leaders)} 只")

    # 4. 信号
    from v2_final.strategy.signal import generate_signal
    portfolio = {"exposure": 0.0, "positions": 0, "single_exposure": 0}
    signal = generate_signal(leaders, sector_rank, portfolio["exposure"])
    logger.info(f"信号: {signal['action']} {signal.get('stock_code','')} conf={signal['confidence']}")

    # 5. 风控
    from v2_final.risk.risk_manager import risk_check, calc_position_size
    ok, reason = risk_check(signal, portfolio)
    signal["position_size"] = calc_position_size(signal["confidence"], portfolio["exposure"])
    logger.info(f"风控: {'✅' if ok else '❌'} {reason}")

    # 6. 执行
    from v2_final.execution.paper import execute
    result = execute(signal, portfolio) if ok else {"status": "blocked", "reason": reason}

    # 7. 输出
    from v2_final.output.reporter import build_report, save_report
    report = build_report(signal, sector_rank, leaders, result, ok)
    path = save_report(report)
    logger.info(f"输出: {path}")
    logger.info(f"完成: {signal['action']} {'成交' if result.get('status')=='filled' else result.get('status')}")


if __name__ == "__main__":
    run()
