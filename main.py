"""
main.py — v2.2 稳定实盘系统
=============================
闭环: 数据 → 板块 → 选股 → 信号 → 风控 → 执行 → 日志 → 分析

用法: python main.py
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v2")


def run():
    logger.info("v2.2 启动")

    # ── 1. 数据 ──
    from v2_final.data.provider import get_market_data
    data = get_market_data()
    if not data["stocks"]:
        logger.warning("数据为空")
        return

    # ── 2. 板块强度 ──
    from v2_final.strategy.sector import calc_sector_strength
    sector_rank = calc_sector_strength(data["sectors"])
    logger.info(f"板块: {sector_rank[0]['name']} {sector_rank[0]['strength']:.1f}")

    # ── 3. v2.1 低价优选选股 ──
    from v2_final.strategy.stock import pick_leaders
    leaders = pick_leaders(data["stocks"], sector_rank)
    logger.info(f"选股: {len(leaders)} 只 (Top: {leaders[0]['name']} {leaders[0]['price']}元)")

    # ── 4. v2.2 自适应信号 ──
    from v2_final.strategy.signal import generate_signal
    from v2_final.analysis.log_analysis import analyze_logs
    from v2_final.risk.risk_manager import check_drawdown

    # 历史分析 + 回撤检测
    stats = analyze_logs()
    equity = [1.0]  # 简化净值曲线
    dd_status = check_drawdown(equity)

    portfolio = {"exposure": 0.0, "positions": 0}
    signal = generate_signal(leaders, sector_rank, portfolio["exposure"],
                             drawdown_status=dd_status, stats=stats)
    logger.info(f"信号: {signal['action']} {signal.get('stock_code','')} "
                f"conf={signal['confidence']} dd={dd_status} wr={stats['win_rate']:.1%}")

    # ── 5. v2.2 动态风控 ──
    from v2_final.risk.risk_manager import risk_check, calc_position_size
    ok, reason = risk_check(signal, portfolio)
    signal["position_size"] = calc_position_size(
        signal["confidence"], portfolio["exposure"],
        volatility=0.4 if dd_status == "OK" else 0.7
    )
    logger.info(f"风控: {'✅' if ok else '❌'} {reason} pos={signal['position_size']:.0%}")

    # ── 6. v2.1 日志记录 ──
    from v2_final.utils.logger import log_signal, log_execution
    log_signal(signal)

    # ── 7. 执行 ──
    from v2_final.execution.paper import execute
    result = execute(signal, portfolio) if ok else {"status": "blocked", "reason": reason}
    log_execution(result)

    # ── 8. 输出 ──
    from v2_final.output.reporter import build_report, save_report
    report = build_report(signal, sector_rank, leaders, result, ok)
    report["v2.2"] = {
        "drawdown_status": dd_status,
        "win_rate": stats["win_rate"],
        "avg_confidence": stats["avg_confidence"],
    }
    path = save_report(report)
    logger.info(f"输出: {path}")
    logger.info(f"完成: {signal['action']} "
                f"{'成交' if result.get('status')=='filled' else result.get('status')} "
                f"| dd={dd_status} wr={stats['win_rate']:.1%}")


if __name__ == "__main__":
    run()
