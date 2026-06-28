"""
main.py — v2.3 多股票组合回测系统
=====================================
完整闭环: 全市场 → 排名 → 分仓 → 组合回测 → 绩效 → 日报

用法: python main.py [--top 5]
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v2")


def run(top_n: int = 5):
    logger.info(f"v2.3 组合回测 — Top {top_n}")

    # ── 1. 全市场数据 ──
    from v2_final.data.provider import get_market_data
    data = get_market_data()
    if not data["stocks"]:
        logger.error("无数据")
        return

    # ── 2. 板块强度 ──
    from v2_final.strategy.sector import calc_sector_strength
    sector_rank = calc_sector_strength(data["sectors"])

    # ── 3. 评分排名 ──
    from v2_final.strategy.ranker import rank_stocks
    ranked = rank_stocks(data["stocks"], sector_rank, top_n=top_n * 4)
    logger.info(f"排名: {len(ranked)} 候选")

    if not ranked:
        logger.warning("无符合条件的候选")
        return

    # ── 4. 分仓分配 ──
    from v2_final.strategy.allocation import allocate_portfolio
    portfolio = allocate_portfolio(ranked, top_n=top_n)

    print()
    print("┌─ 组合持仓 ────────────────────────")
    for i, p in enumerate(portfolio):
        print(f"│ {i+1}. {p['name']:8s} {p['code']}  "
              f"score={p['score']:.1f} weight={p['weight']:.0%}  ¥{p['price']}")
    print("└──────────────────────────────────")

    # ── 5. 组合回测 ──
    from v2_final.backtest.portfolio_bt import backtest_portfolio, fetch_prices_for_portfolio

    logger.info("拉取历史价格...")
    price_data = fetch_prices_for_portfolio(portfolio)
    bt = backtest_portfolio(portfolio, price_data)

    m = bt["metrics"]
    print()
    print(f"  组合回测: 收益 {m['total_return']:+.1f}%  回撤 {m['max_drawdown']:.1f}%  "
          f"sharpe={m['sharpe']}  win_rate={m['win_rate']:.0%}  vol={m['volatility']:.1f}%")

    # ── 6. 绩效分析 ──
    from v2_final.analysis.performance import analyze_equity
    perf = analyze_equity(bt["equity_curve"])
    print(f"  绩效评分: {perf['score']:.0f}/100 ({perf['rating']})  sharpe={perf['sharpe']}")

    # ── 7. 日报 ──
    from v2_final.report.daily_report import generate_report, save_report, print_summary

    report = generate_report(
        symbol=f"PORTFOLIO-{top_n}",
        signal={"portfolio": portfolio, "metrics": m},
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
