"""
main.py — v2.5 最终稳定版
=============================
闭环: 市场过滤 → 行业过滤 → 选股 → 排名 → 分仓 → 回测 → 策略评分 → 门控 → 日报

用法: python main.py [--top 5]
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v2")


def run(top_n: int = 5):
    logger.info(f"v2.5 启动 — Top {top_n}")

    # ── v2.4 市场状态过滤 ──
    from v2_final.strategy.market_state import get_market_state
    market_state = get_market_state()

    if market_state == "NO_TRADE":
        logger.warning("市场状态 NO_TRADE — 跳过交易")
        from v2_final.report.daily_report import generate_report, save_report, print_summary
        report = generate_report("MARKET", {"action": "HOLD"}, {},
                                  {"action": "SKIP", "reason": "market NO_TRADE"})
        save_report(report)
        print_summary(report)
        return

    # ── 数据 ──
    from v2_final.data.provider import get_market_data
    data = get_market_data()
    if not data["stocks"]:
        logger.error("无数据")
        return

    # ── v2.4 行业过滤 ──
    from v2_final.strategy.sector import calc_sector_strength
    from v2_final.strategy.sector_filter import get_strong_sectors, filter_stocks_by_sector

    sector_rank = calc_sector_strength(data["sectors"])
    strong_sectors = get_strong_sectors(data["sectors"], top_n=5)
    filtered = filter_stocks_by_sector(data["stocks"], strong_sectors,
                                        max_price=60, min_momentum=1.5)

    if len(filtered) < top_n:
        logger.warning(f"候选不足: {len(filtered)} < {top_n}")
        return

    # ── v2.3 排名 + 分仓 ──
    from v2_final.strategy.ranker import rank_stocks
    from v2_final.strategy.allocation import allocate_portfolio

    ranked = rank_stocks(filtered, sector_rank, top_n=top_n * 4)
    portfolio = allocate_portfolio(ranked, top_n=top_n)

    print()
    print("┌─ 组合持仓 ────────────────────────")
    for i, p in enumerate(portfolio):
        print(f"│ {i+1}. {p['name']:8s} {p['code']}  "
              f"score={p['score']:.1f} w={p['weight']:.0%}  ¥{p['price']}")
    print("└──────────────────────────────────")

    # ── v2.3 组合回测 ──
    from v2_final.backtest.portfolio_bt import backtest_portfolio, fetch_prices_for_portfolio
    logger.info("拉取历史价格...")
    price_data = fetch_prices_for_portfolio(portfolio)
    bt = backtest_portfolio(portfolio, price_data)
    m = bt["metrics"]

    print(f"\n  回测: {m['total_return']:+.1f}%  dd={m['max_drawdown']:.1f}%  "
          f"sharpe={m['sharpe']}  wr={m['win_rate']:.0%}")

    # ── v2.5 策略健康监控 ──
    from v2_final.analysis.rolling_stats import RollingStats
    from v2_final.analysis.health_score import compute_health_score
    from v2_final.utils.equity_tracker import EquityTracker

    tracker = EquityTracker()
    tracker.load()

    # 更新净值追踪
    for v in bt["equity_curve"]:
        tracker.update(v)
    tracker.save()

    # 滚动统计
    rolling = RollingStats(window=20)
    rolling.update(bt["equity_curve"])
    rstats = rolling.stats()

    # 健康评分
    health = compute_health_score({**m, "sharpe": m.get("sharpe", 0)})

    print(f"  健康: {health['health_score']}/100 {health['rating']}")
    print(f"  滚动20d: wr={rstats['win_rate']:.0%} vol={rstats['volatility']:.1%} sharpe={rstats['sharpe']}")
    print(f"  净值追踪: {tracker.summary()['n_days']}天 dd={tracker.current_drawdown():.1f}%")

    # ── v2.5 策略门控 ──
    from v2_final.strategy.strategy_gate import get_verdict
    verdict = get_verdict(m)

    print(f"  策略评分: {verdict['score']}/3 → {verdict['verdict']}")
    print()

    # ── 日报 ──
    from v2_final.report.daily_report import generate_report, save_report, print_summary
    report = generate_report(
        symbol=f"PORTFOLIO-{top_n}",
        signal={"portfolio": portfolio, "metrics": m, "verdict": verdict},
        backtest_result=bt,
    )
    save_report(report)
    print_summary(report)


if __name__ == "__main__":
    top = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
    run(top)
