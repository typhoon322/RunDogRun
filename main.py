"""
main.py — v2.2-AK 数据增强回测验证版
=======================================
完整闭环: 历史数据 → 回测 → 绩效 → 日报 → 今日本盘信号

用法: python main.py [--symbol 000001]
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v2")


def generate_signal_from_df(df):
    """从历史 DataFrame 生成信号 (用于回测)"""
    if len(df) < 5:
        return {"action": "HOLD", "confidence": 0}

    latest = df.iloc[-1]
    momentum = float(latest.get("pct", 0))
    close = float(latest.get("close", 0))

    # 5日均线
    ma5 = df["close"].rolling(5).mean().iloc[-1]

    trend = close > ma5
    if momentum > 3 and trend:
        return {"action": "BUY", "confidence": 0.75}
    elif momentum < -5:
        return {"action": "SELL", "confidence": 0.80}
    return {"action": "HOLD", "confidence": 0.40}


def run(symbol: str = "000001"):
    logger.info(f"v2.2-AK 启动 — 标的: {symbol}")

    # ── 1. 获取历史 K 线 ──
    from v2_final.data.provider import get_daily_data
    df = get_daily_data(symbol, start_date="20230101")
    if df.empty or len(df) < 30:
        logger.error("历史数据不足")
        return
    logger.info(f"数据: {len(df)} 条日线 ({df.iloc[0]['date']} → {df.iloc[-1]['date']})")

    # ── 2. 回测 ──
    from v2_final.backtest.backtester import backtest
    bt = backtest(df, generate_signal_from_df, initial_cash=1.0, position_size=0.30)
    m = bt["metrics"]
    logger.info(f"回测: 收益{m['total_return_pct']:+.1f}% "
                f"回撤{m['max_drawdown_pct']:.1f}% 胜率{m['win_rate']:.0%} "
                f"{m['total_closed_trades']}笔交易")

    # ── 3. 绩效分析 ──
    from v2_final.analysis.performance import analyze_equity
    perf = analyze_equity(bt["equity_curve"])
    logger.info(f"绩效: score={perf['score']} sharpe={perf['sharpe']}")
    logger.info(f"  收益{perf['total_return']:.1f}% 回撤{perf['max_drawdown']:.1f}% 胜率{perf['win_rate']:.0%}")

    # ── 4. 今日本盘信号 ──
    from v2_final.data.provider import get_market_data
    from v2_final.strategy.sector import calc_sector_strength
    from v2_final.strategy.stock import pick_leaders
    from v2_final.strategy.signal import generate_signal

    data = get_market_data()
    sector_rank = calc_sector_strength(data["sectors"]) if data["sectors"] else []
    leaders = pick_leaders(data["stocks"], sector_rank) if data["stocks"] else []
    portfolio = {"exposure": 0.0, "positions": 0}
    live_sig = generate_signal(leaders, sector_rank, portfolio["exposure"])

    # ── 5. 日报 ──
    from v2_final.report.daily_report import generate_report, save_report, print_summary
    report = generate_report(symbol, live_sig, bt, live_sig)
    save_report(report)
    print_summary(report)

    return report


if __name__ == "__main__":
    symbol = sys.argv[2] if len(sys.argv) >= 3 and sys.argv[1] == "--symbol" else "000001"
    run(symbol)
