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

    # ── v2.3 组合回测 (优先本地缓存) ──
    from v2_final.backtest.fast_backtest import backtest_from_cache
    from v2_final.data.collector import get_cache_stats

    cache_stats = get_cache_stats()
    logger.info(f"数据仓库: {cache_stats['cached_stocks']} 只缓存({cache_stats['total_size_kb']:.0f}KB)")

    bt = backtest_from_cache(portfolio)
    m = bt["metrics"]

    print(f"\n  回测: {m['total_return']:+.1f}%  dd={m['max_drawdown']:.1f}%  "
          f"sharpe={m['sharpe']}  wr={m['win_rate']:.0%}")

    # ── v2.5 统一监控 ──
    from v2_final.analysis.monitor import analyze, RollingMonitor
    from v2_final.utils.equity_tracker import EquityTracker

    result = analyze(bt["equity_curve"])

    # 滚动监控
    monitor = RollingMonitor(window=20)
    tracker = EquityTracker()
    tracker.load()
    for v in bt["equity_curve"]:
        tracker.update(v)
        monitor.update(v, result["health_score"])
    tracker.save()

    print(f"  监控: {result['rating']} {result['health_score']}/100 → {result['status']}")
    print(f"  趋势: {monitor.trend()}  dd_now={monitor.current_drawdown():.1f}%")
    print(f"  评分: wr={result['breakdown']['win_rate_score']} "
          f"dd={result['breakdown']['drawdown_score']} "
          f"vol={result['breakdown']['volatility_score']}")
    print(f"  建议: {result['note']}")

    # ── 日报 ──
    from v2_final.report.daily_report import generate_report, save_report, print_summary
    report = generate_report(
        symbol=f"PORTFOLIO-{top_n}",
        signal={"portfolio": portfolio, "metrics": m, "status": result["status"]},
        backtest_result=bt,
    )
    report["monitor"] = {
        "status": result["status"],
        "health_score": result["health_score"],
        "rating": result["rating"],
        "trend": monitor.trend(),
        "note": result["note"],
    }
    save_report(report)
    from v2_final.report.daily_report import generate_markdown
    generate_markdown(report)
    print_summary(report)

    # 最终结论
    if result["status"] == "STOP":
        print(f"\n  ⛔ {result['note']}")
    elif result["status"] == "CAUTION":
        print(f"\n  ⚡ {result['note']}")
    else:
        print(f"\n  ✅ {result['note']}")


if __name__ == "__main__":
    top = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
    run(top)
