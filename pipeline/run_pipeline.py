"""
pipeline/run_pipeline.py — v2.5 Final 统一闭环流水线
============================================================
唯一执行入口: GitHub Actions 定时触发 → 本地也可手动运行

闭环:
  Registry扫描 → Universe生成 → 数据补齐 → 市场过滤 →
  行业过滤 → 选股排名 → 组合配置 → 回测(Registry) →
  监控评分 → 日报输出 → output/

用法:
  python pipeline/run_pipeline.py [--top 5]
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pipeline")

OUTPUT_DIR = "output"


def ensure_output_dir():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path("data/outputs").mkdir(parents=True, exist_ok=True)


def save_json(data: dict, filename: str):
    """双写: output/ + data/outputs/ (兼容)"""
    for d in [OUTPUT_DIR, "data/outputs"]:
        path = os.path.join(d, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"  ↳ 写入 {path}")


def run_pipeline(top_n: int = 5):
    """主流水线 — 单次执行完成全部环节"""
    t0 = datetime.now()
    steps = []

    def step(name: str, status: str, detail: str = ""):
        steps.append({
            "step": name, "status": status,
            "detail": detail,
            "time": datetime.now().strftime("%H:%M:%S"),
        })

    print()
    print("═" * 50)
    print("  🚀 PIPELINE v2.5 Final — 闭环启动")
    print("═" * 50)
    ensure_output_dir()

    # ═══════════════════════════════════════════════
    # ① 数据注册扫描
    # ═══════════════════════════════════════════════
    from core.data_registry import DataRegistry
    registry = DataRegistry()
    registry.reload()
    all_codes = registry.get_all()
    stats = registry.stats()

    print(f"\n📦 ① REGISTRY: {stats['total_csv']} CSV 可调度")
    step("01_registry", "ok", f"{stats['total_csv']} CSV")

    # ═══════════════════════════════════════════════
    # ② Universe 生成 (行业轮动 + 稳定性)
    # ═══════════════════════════════════════════════
    from data.build_stable_universe import build_stable
    universe = build_stable(top_n=300)
    print(f"📊 ② UNIVERSE: {len(universe)} 只 (stable merge)")
    step("02_universe", "ok", f"{len(universe)} stocks")

    # ═══════════════════════════════════════════════
    # ③ 数据补齐 (关键: 确保 Universe 中每只都有 CSV)
    # ═══════════════════════════════════════════════
    from data.sync_data import sync_universe
    if universe:
        sync_universe(universe, max_new=30)
        print(f"📥 ③ SYNC: Universe 数据已补齐")
        step("03_sync", "ok", f"synced for {len(universe)} codes")
    else:
        step("03_sync", "skip", "empty universe")

    # ═══════════════════════════════════════════════
    # ④ 市场状态检查
    # ═══════════════════════════════════════════════
    from v2_final.strategy.market_state import get_market_state
    market_state = get_market_state()
    print(f"📡 ④ MARKET: {market_state}")
    step("04_market", "ok", market_state)

    if market_state == "NO_TRADE":
        print("  ⛔ 市场状态 NO_TRADE — 跳过选股, 仅输出空日报")
        step("05_pipeline", "skip", "market NO_TRADE")
        report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "version": "2.5-final",
            "pipeline_status": "SKIPPED",
            "reason": "market NO_TRADE",
            "universe_size": len(universe),
            "registry_stats": stats,
        }
        save_json(report, "daily_report.json")
        _save_log(steps, t0)
        return

    # ═══════════════════════════════════════════════
    # ⑤ 数据获取
    # ═══════════════════════════════════════════════
    from v2_final.data.provider import get_market_data
    data = get_market_data()
    n_stocks = len(data.get("stocks", []))
    print(f"📡 ⑤ DATA: {n_stocks} 只全市场股票")
    step("05_fetch", "ok", f"{n_stocks} stocks")

    if n_stocks < 50:
        logger.error("数据不足, 终止")
        step("06_pipeline", "fail", f"only {n_stocks} stocks")
        _save_log(steps, t0)
        return

    # ═══════════════════════════════════════════════
    # ⑥ 行业过滤
    # ═══════════════════════════════════════════════
    from v2_final.strategy.sector import calc_sector_strength
    from v2_final.strategy.sector_filter import get_strong_sectors, filter_stocks_by_sector

    sector_rank = calc_sector_strength(data.get("sectors", {}))
    strong_sectors = get_strong_sectors(data.get("sectors", {}), top_n=5)
    print(f"🏭 ⑥ SECTOR: {len(strong_sectors)} 强行业")
    step("06_sector", "ok", f"{len(strong_sectors)} strong sectors")

    filtered = filter_stocks_by_sector(
        data["stocks"], strong_sectors,
        max_price=60, min_momentum=1.5,
    )
    print(f"🔍 ⑦ FILTER: {len(filtered)} 候选 (行业+价格+动量)")
    step("07_filter", "ok", f"{len(filtered)} candidates")

    if len(filtered) < top_n:
        logger.warning(f"候选不足: {len(filtered)} < {top_n}")
        step("08_pipeline", "skip", f"only {len(filtered)} candidates")
        _save_log(steps, t0)
        return

    # ═══════════════════════════════════════════════
    # ⑧ 排名 + 组合配置
    # ═══════════════════════════════════════════════
    from v2_final.strategy.ranker import rank_stocks
    from v2_final.strategy.allocation import allocate_portfolio

    ranked = rank_stocks(filtered, sector_rank, top_n=top_n * 4)
    portfolio = allocate_portfolio(ranked, top_n=top_n)
    step("08_allocate", "ok", f"{len(portfolio)} stocks")

    print()
    print("  ┌─ 组合持仓 ────────────────────────")
    for i, p in enumerate(portfolio):
        print(f"  │ {i+1}. {p['name']:8s} {p['code']}  "
              f"score={p['score']:.1f} w={p['weight']:.0%}  ¥{p['price']}")
    print("  └──────────────────────────────────")

    # ═══════════════════════════════════════════════
    # ⑨ 回测 (强制走 DataRegistry)
    # ═══════════════════════════════════════════════
    from v2_final.backtest.fast_backtest import backtest_from_cache

    bt = backtest_from_cache(portfolio)
    m = bt.get("metrics", {})
    equity_curve = bt.get("equity_curve", [1.0])

    print(f"\n  📈 回测: {m.get('total_return', 0):+.1f}%  "
          f"dd={m.get('max_drawdown', 0):.1f}%  "
          f"sharpe={m.get('sharpe', 0)}  wr={m.get('win_rate', 0):.0%}")
    step("09_backtest", "ok", f"return={m.get('total_return', 0):+.1f}%")

    # 保存 equity_curve (output/ 主输出)
    save_json({"curve": equity_curve, "metrics": m}, "equity_curve.json")

    # ═══════════════════════════════════════════════
    # ⑩ 监控 + 一致性检查
    # ═══════════════════════════════════════════════
    from v2_final.analysis.monitor import analyze
    from core.data_consistency import check_csv_integrity

    result = analyze(equity_curve)
    csv_check = check_csv_integrity()

    print(f"  🩺 监控: {result['rating']} {result['health_score']}/100 → {result['status']}")
    print(f"  📋 一致性: CSV {csv_check['ok']}/{csv_check['total']} OK")
    print(f"  💡 建议: {result['note']}")
    step("10_monitor", "ok", f"score={result['health_score']} status={result['status']}")

    # ═══════════════════════════════════════════════
    # ⑪ 日报输出 (闭环终产物)
    # ═══════════════════════════════════════════════
    from v2_final.report.daily_report import generate_report, save_report, print_summary, generate_markdown

    report = generate_report(
        symbol=f"PORTFOLIO-{top_n}",
        signal={"portfolio": portfolio, "metrics": m, "status": result["status"]},
        backtest_result=bt,
    )
    report["monitor"] = {
        "status": result["status"],
        "health_score": result["health_score"],
        "rating": result["rating"],
        "trend": "stable →",
        "note": result["note"],
    }
    report["consistency"] = {
        "csv_ok": csv_check["ok"],
        "csv_total": csv_check["total"],
        "registry_total": stats["total_csv"],
    }

    save_report(report)           # → data/outputs/daily_report.json
    save_json(report, "daily_report.json")  # → output/daily_report.json
    generate_markdown(report)
    print_summary(report)
    step("11_report", "ok", f"status={result['status']} score={result['health_score']}")

    # ═══════════════════════════════════════════════
    # ⑫ v2.6 日报 (Markdown + 微信版)
    # ═══════════════════════════════════════════════
    from report.generate_report import generate_report as gen_v26_report
    gen_v26_report()
    step("12_v26_report", "ok", "md + wechat")
    print("  📝 v2.6 日报: daily_report.md + daily_report_wechat.txt")

    # ═══════════════════════════════════════════════
    # 保存 Pipeline 日志
    # ═══════════════════════════════════════════════
    _save_log(steps, t0)

    # 最终结论
    print()
    if result["status"] == "STOP":
        print(f"  ⛔ {result['note']}")
    elif result["status"] == "CAUTION":
        print(f"  ⚡ {result['note']}")
    else:
        print(f"  ✅ {result['note']}")
    print("═" * 50)
    print("  ✅ PIPELINE COMPLETE")
    print("═" * 50)


def _save_log(steps: list, t0: datetime):
    ok_count = sum(1 for s in steps if s["status"] == "ok")
    fail_count = sum(1 for s in steps if s["status"] == "fail")
    elapsed = (datetime.now() - t0).total_seconds()

    plog = {
        "pipeline": "v2.5-final",
        "started": t0.isoformat(),
        "elapsed_sec": round(elapsed, 1),
        "total": len(steps),
        "ok_count": ok_count,
        "fail_count": fail_count,
        "steps": steps,
    }
    save_json(plog, "pipeline_log.json")
    print(f"\n  ⏱ 耗时: {elapsed:.0f}s  |  {'✅ 全通过' if fail_count == 0 else f'❌ {fail_count} 失败'}")


if __name__ == "__main__":
    top = 5
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
    run_pipeline(top)
