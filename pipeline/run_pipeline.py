"""
pipeline/run_pipeline.py — V3 FINAL 生命周期状态机驱动流水线
===============================================================
唯一执行入口: GitHub Actions 定时触发 → 本地也可手动运行

V3 FINAL 四阶段状态机:
  COLLECT_ONLY → WARM_UP → ACTIVE → (MONITORING) → 降级回滚
  STATE 决定行为, 不许绕过状态机

用法:
  python pipeline/run_pipeline.py [--top 5] [--data-only]
  --data-only: 强制 COLLECT_ONLY (跳过策略计算)
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 北京时间
CN_TZ = timezone(timedelta(hours=8))
def now_cn():
    return datetime.now(CN_TZ)

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


def run_pipeline(top_n: int = 5, data_only: bool = False):
    """主流水线 — 单次执行完成全部环节

    V3 FINAL: 行为由 core.state_machine 决定, 不允许绕过。
    """
    from core.state_machine import (
        load_state as load_sm_state, save_state, update_state, compute_stats,
        should_run_monitoring, record_monitor_check, get_state_summary,
        STATE_BEHAVIOR, COLLECT_ONLY, WARM_UP, ACTIVE, MONITORING,
        STATE_EMOJI, STATE_LABELS,
    )

    t0 = now_cn()
    steps = []

    # ═══ 加载/初始化状态机 ═══
    sm_state = load_sm_state()
    current_state = sm_state["state"]

    # --data-only 手动覆盖
    if data_only:
        current_state = COLLECT_ONLY
    behavior = STATE_BEHAVIOR.get(current_state, STATE_BEHAVIOR[COLLECT_ONLY])

    emoji = STATE_EMOJI.get(current_state, "❓")
    label = STATE_LABELS.get(current_state, current_state)

    def step(name: str, status: str, detail: str = ""):
        steps.append({
            "step": name, "status": status,
            "detail": detail,
            "time": now_cn().strftime("%H:%M:%S"),
        })

    print()
    print("═" * 60)
    print(f"  {emoji} {label} — V3 FINAL 状态机驱动")
    print(f"  STATE: {current_state} | 允许交易: {'是' if behavior['execute_trade'] else '否'}")
    print("═" * 60)
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
        sync_universe(universe, max_new=60)
        print(f"📥 ③ SYNC: Universe 数据已补齐")
        step("03_sync", "ok", f"synced for {len(universe)} codes")
    else:
        step("03_sync", "skip", "empty universe")

    # ═══════════════════════════════════════════════
    # ③b 交易日统计 (必跑)
    # ═══════════════════════════════════════════════
    from core.data_days import save_collection_days
    days_info = save_collection_days()
    min_days = days_info["per_stock_stats"]["min_days"]
    step("03b_data_days", "ok", f"{days_info['total_trading_days']} trading days, min={min_days}")
    print(f"  📅 交易日: {days_info['total_trading_days']}天 | min_days={min_days} | avg={days_info['per_stock_stats']['avg_days']}")

    # ═══════════════════════════════════════════════
    # STATE: COLLECT_ONLY — 到此为止, 跳过策略计算
    # ═══════════════════════════════════════════════
    if current_state == COLLECT_ONLY:
        days_threshold = 10  # 从状态机取: min_days >= 10 可进入 WARM_UP

        # 尝试状态转换
        sm_stats = compute_stats(min_days=min_days)
        new_sm = update_state(sm_stats)
        new_state = new_sm["state"]

        remaining = max(0, days_threshold - min_days)
        report = {
            "date": now_cn().strftime("%Y-%m-%d"),
            "timestamp": now_cn().isoformat(),
            "version": "3.0-final",
            "state_machine": get_state_summary(),
            "pipeline_status": "COLLECT_ONLY",
            "registry_stats": stats,
            "universe_size": len(universe),
            "data_days": days_info,
            "warmup": {
                "min_days": min_days,
                "target_days": days_threshold,
                "remaining_days": remaining,
                "progress": f"{min_days}/{days_threshold}",
                "next_phase": "WARM_UP",
            },
        }
        save_json(report, "daily_report.json")
        _save_log(steps, t0)

        print()
        print(f"  ❄️ COLLECT_ONLY: min_days={min_days}/{days_threshold}")
        if new_state != COLLECT_ONLY:
            print(f"  🎉 状态转换: COLLECT_ONLY → {new_state}")
        elif remaining > 0:
            print(f"  ⏳ 还需约 {remaining} 个交易日进入 WARM_UP (统计预热)")
        print("═" * 60)
        return

    # ═══════════════════════════════════════════════
    # STATE: WARM_UP — 评分+信号+IC/分桶, 不交易
    # ═══════════════════════════════════════════════
    if current_state == WARM_UP:
        logger.info(f"🔥 WARM_UP (min_days={min_days}) — 评分+信号+IC, 不交易")

        # ④ 市场状态
        market_state = "UNKNOWN"
        try:
            from v2_final.strategy.market_state import get_market_state
            market_state = get_market_state()
            print(f"📡 ④ MARKET: {market_state}")
            step("04_market", "ok", market_state)
        except Exception as e:
            step("04_market", "skip", str(e)[:30])

        # ⑤ 数据获取 + ⑥⑦⑧ 评分
        ranked = []
        try:
            from v2_final.data.provider import get_market_data
            data = get_market_data()
            n_stocks = len(data.get("stocks", []))
            print(f"📡 ⑤ DATA: {n_stocks} 只全市场股票")
            step("05_fetch", "ok" if n_stocks > 0 else "skip", f"{n_stocks} stocks")

            if n_stocks >= 50:
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
                print(f"🔍 ⑦ FILTER: {len(filtered)} 候选")
                step("07_filter", "ok", f"{len(filtered)} candidates")

                from v2_final.strategy.ranker import rank_stocks
                ranked = rank_stocks(filtered, sector_rank, top_n=top_n * 4)
                print(f"📊 ⑧ RANK: {len(ranked)} 只评分完成 (Phase 2: 不做组合配置)")
                step("08_rank", "ok", f"{len(ranked)} ranked")

                # ⑧b 信号记录 — Phase 2 核心价值: 积累信号用于 IC 计算
                from core.signal_logger import log_signals
                # ranked 没有 weight/price 字段, 补充
                for r in ranked:
                    r.setdefault("weight", 0)
                log_signals(ranked, market_state)
                step("08b_signal_log", "ok", f"{len(ranked)} signals logged")
                print(f"  📝 信号已记录: {len(ranked)} 条")
            else:
                step("08_rank", "skip", "insufficient data for scoring")
                print("  ⚠️ 数据不足, 跳过评分 (下次 GH Actions 可能成功)")
        except Exception as e:
            step("05_fetch", "skip", str(e)[:30])
            print(f"  ⚠️ 数据获取失败: {e}")

        # ⑮ 前瞻收益回填
        try:
            from analytics.forward_returns import compute as compute_fwd
            compute_fwd()
            step("15_fwd_returns", "ok", "forward returns computed")
        except Exception as e:
            step("15_fwd_returns", "skip", str(e)[:30])

        # ⑯ IC + 分桶
        ic_rpt = {}
        bucket_rpt = {}
        ic_val = None
        try:
            from analytics.ic import ic_report
            ic_rpt = ic_report()
            ic_val = ic_rpt.get("ic_5d", {}).get("ic")
            step("16_ic", "ok", f"IC(5d)={ic_val}")
        except Exception as e:
            step("16_ic", "skip", str(e)[:30])

        try:
            from analytics.bucket import bucket_report
            bucket_rpt = bucket_report()
            step("17_bucket", "ok", "bucket analysis done")
        except Exception as e:
            step("17_bucket", "skip", str(e)[:30])

        # ═══ Score 稳定性 ═══
        stability = {}
        try:
            from stats.stability import compute_stability
            stability = compute_stability()
            step("17b_stability", "ok" if stability.get("stable") else "skip",
                 f"stable={stability.get('stable')}")
        except Exception as e:
            step("17b_stability", "skip", str(e)[:30])

        # ═══ 状态机: WARM_UP → ACTIVE? ═══
        signal_count = 0
        try:
            from core.signal_logger import load_history
            signal_count = len(load_history())
        except Exception:
            pass

        sm_stats = compute_stats(
            min_days=min_days,
            signal_count=signal_count,
            ic_5d=ic_val,
        )
        sm_stats["score_stable"] = stability.get("stable", False)

        new_sm = update_state(sm_stats)
        new_state = new_sm["state"]

        # ═══ WARM_UP 统计摘要 ═══
        warmup_stats = _build_warmup_stats(ranked, ic_rpt, bucket_rpt)
        warmup_stats["stability"] = stability

        report = {
            "date": now_cn().strftime("%Y-%m-%d"),
            "timestamp": now_cn().isoformat(),
            "version": "3.0-final",
            "state_machine": get_state_summary(),
            "pipeline_status": "WARM_UP",
            "registry_stats": stats,
            "universe_size": len(universe),
            "data_days": days_info,
            "market_state": market_state,
            "warmup": {
                "min_days": min_days,
                "target_days": 30,
                "remaining_days": max(0, 30 - min_days),
                "progress": f"{min_days}/30",
                "next_phase": "ACTIVE",
            },
            "warmup_stats": warmup_stats,
            "stability": stability,
        }
        save_json(report, "daily_report.json")
        _save_log(steps, t0)

        print()
        print(f"  🔥 WARM_UP: min_days={min_days}")
        print(f"  📊 评分: {warmup_stats['score_count']} 只 | "
              f"信号累计: {warmup_stats['signal_count']} 条")
        if ic_val is not None:
            q = "🟢有效" if ic_val > 0.03 else ("⏳积累中" if ic_val >= 0 else "🔴反向")
            print(f"  📈 IC(5d): {ic_val:+.4f} {q}")
        if stability.get("stable"):
            print(f"  ✅ 稳定: drift={stability.get('mean_drift', '?')}")
        if new_state != WARM_UP:
            print(f"  🎉 状态转换: WARM_UP → {new_state}")
        print("═" * 60)
        return

    # ═══════════════════════════════════════════════
    # STATE: ACTIVE/MONITORING — 完整交易闭环
    # ═══════════════════════════════════════════════
    logger.info(f"🚀 ACTIVE 完整交易 (min_days={min_days})")

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
            "date": now_cn().strftime("%Y-%m-%d"),
            "timestamp": now_cn().isoformat(),
            "version": "3.0-final",
            "state_machine": get_state_summary(),
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
    # ⑧b v3.0 信号记录
    # ═══════════════════════════════════════════════
    from core.signal_logger import log_signals
    log_signals(portfolio, market_state)
    step("08b_signal_log", "ok", f"{len(portfolio)} signals")

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

    print(f"  🩺 监控: {result.get('rating','?')} {result['health_score']}/100 → {result['status']}")
    print(f"  📋 一致性: CSV {csv_check['ok']}/{csv_check['total']} OK")
    print(f"  💡 建议: {result['note']}")
    step("10_monitor", "ok", f"score={result['health_score']} status={result['status']}")

    # ═══════════════════════════════════════════════
    # ⑩b v3 Lite 执行规则判定
    # ═══════════════════════════════════════════════
    from core.execution_rules import decide, print_decision

    # 从组合中取趋势/流动性/估值的中位数作为当前市场环境
    trends = [p.get("trend", 50) for p in portfolio] if portfolio else [50]
    flows = [p.get("flow", 50) for p in portfolio] if portfolio else [50]
    values = [p.get("value", 50) for p in portfolio] if portfolio else [50]

    avg_trend = sum(trends) / len(trends) if trends else 50
    avg_flow = sum(flows) / len(flows) if flows else 50
    avg_score = sum(p.get("score", 0) for p in portfolio) / len(portfolio) if portfolio else 0

    # 归一化 score 到 0-100 区间
    norm_score = min(100, max(0, avg_score / 12.0 * 100)) if portfolio else 0
    avg_value = sum(values) / len(values) if values else 50

    # ═══════════════════════════════════════════════
    # V3 FINAL PATCH: Decision Engine (唯一决策入口)
    # ═══════════════════════════════════════════════
    from execution.decision_engine import decide as final_decide

    decision = final_decide(
        system_score=norm_score,
        trend=avg_trend,
        flow=avg_flow,
        value=avg_value,
    )
    print(f"  🎯 Decision Engine: {decision['emoji']} {decision['action']} — {decision['reason']}")
    step("10b_decision", "ok", f"action={decision['action']}")

    # ═══════════════════════════════════════════════
    # V3 FINAL PATCH: Signal Snapshot (冻结信号)
    # ═══════════════════════════════════════════════
    from signals.snapshot import create_snapshot
    for p in portfolio:
        create_snapshot(
            stock_code=p["code"],
            stock_name=p["name"],
            decision=decision,
            entry_price=p["price"],
        )
    step("10c_snapshot", "ok", f"{len(portfolio)} snapshots locked")

    # ═══════════════════════════════════════════════
    # ⑩d 仓位计算 + 月度锁定
    # ═══════════════════════════════════════════════
    from core.execution_rules import calc_position_size, get_cooling_status
    from core.monthly_lock import status as lock_status

    cooling = get_cooling_status()
    position = calc_position_size(norm_score, avg_trend, avg_flow,
                                  cooling.get("consecutive_losses", 0))
    lock = lock_status()

    print(f"  💰 仓位: {position['target_pct']:.0%} — {position['reason']}")
    print(f"  🔒 参数锁定: {lock['status_msg']}")

    step("10c_position", "ok", f"target={position['target_pct']:.0%} {position['reason']}")

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
        "rating": result.get("rating", ""),
        "trend": "stable →",
        "note": result["note"],
    }
    # v3 FINAL: 执行决策
    report["execution"] = {
        "decision": decision["action"],
        "emoji": decision["emoji"],
        "can_buy": decision["allow_trade"],
        "can_hold": decision["allow_hold"],
        "in_danger": decision["action"] in ("EXIT", "REDUCE"),
        "details": [decision["reason"]],
        "position_change": decision["position_change"],
        "factors": {
            "trend": round(avg_trend, 1),
            "flow": round(avg_flow, 1),
            "score": round(norm_score, 1),
        },
    }
    # v3 FINAL: 仓位 + 锁定
    report["position"] = {
        "target_pct": position["target_pct"],
        "reason": position["reason"],
        "compressed": position["compressed"],
        "cooling": cooling,
    }
    report["lock"] = {
        "version": lock["version"],
        "can_modify": lock["can_modify"],
        "status_msg": lock["status_msg"],
        "next_allowed": lock["next_allowed"],
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
    print("  📝 v2.8 日报: daily_report.md + daily_report_wechat.txt")

    # ═══════════════════════════════════════════════
    # ⑬ v2.8 系统健康评分
    # ═══════════════════════════════════════════════
    from report.system_health import system_health_score, print_health
    sys_health = system_health_score()
    print_health(sys_health)
    step("13_system_health", "ok", f"score={sys_health['score']} {sys_health['level']}")

    # ═══════════════════════════════════════════════
    # ⑭ 交易日统计
    # ═══════════════════════════════════════════════
    from core.data_days import save_collection_days
    days_info = save_collection_days()
    step("14_collection_days", "ok", f"{days_info['total_trading_days']} trading days")
    print(f"  📅 交易日: {days_info['total_trading_days']}天 ({days_info['date_range']})")

    # ═══════════════════════════════════════════════
    # ⑮ v3.0 前瞻收益回填
    # ═══════════════════════════════════════════════
    from analytics.forward_returns import compute as compute_fwd
    compute_fwd()
    step("15_fwd_returns", "ok", "forward returns computed")

    # ═══════════════════════════════════════════════
    # ⑯ v3.0 IC + 分桶 + 权重优化
    # ═══════════════════════════════════════════════
    from analytics.ic import ic_report
    ic_rpt = ic_report()
    ic_val = ic_rpt.get("ic_5d", {}).get("ic")
    step("16_ic", "ok", f"IC(5d)={ic_val}")

    from analytics.bucket import bucket_report
    bucket_report()
    step("17_bucket", "ok", "bucket analysis done")

    # 简易因子 IC (从 rawer 实际使用的因子)
    # momentum≈change_pct, volume≈成交额, price_value≈1/price, sector≈板块强度
    # IC 简化: 当前先用 score 的总 IC 决定是否调权, 因子级 IC 需更多数据积累
    step("18_optimizer", "skip", "need more signal data for factor-level IC")

    # ═══════════════════════════════════════════════
    # ⑲ V3 FINAL PATCH: Standard Report (统一格式)
    # ═══════════════════════════════════════════════
    from report.standard_report import generate as gen_std_report
    std_report = gen_std_report()
    step("19_standard_report", "ok", f"trades={std_report.get('system_health',{}).get('total_trades',0)}")

    # ═══════════════════════════════════════════════
    # ⑳ V3 FINAL: MONITORING 检查 (每7天)
    # ═══════════════════════════════════════════════
    monitor_result = None
    try:
        if should_run_monitoring():
            from report.monitor import run_monitoring_check, print_monitor
            monitor_result = run_monitoring_check()
            record_monitor_check(monitor_result)
            print_monitor(monitor_result)
            step("20_monitoring", "ok", f"overall={monitor_result['overall']} "
                 f"health={monitor_result['health_score']}")

            # 如触发降级, 更新状态机
            if monitor_result.get("should_degrade"):
                sm_stats = compute_stats(
                    min_days=min_days,
                    ic_5d=ic_val,
                )
                sm_stats["performance_drop"] = True
                new_sm = update_state(sm_stats)
                print(f"  🚨 系统降级: ACTIVE → {new_sm['state']}")
                step("20b_degrade", "warn", f"degraded to {new_sm['state']}")
        else:
            step("20_monitoring", "skip", "not due yet")
    except Exception as e:
        step("20_monitoring", "skip", str(e)[:30])

    # ═══════════════════════════════════════════════
    # ㉑ 状态机: ACTIVE 状态更新 + 降级检查
    # ═══════════════════════════════════════════════
    sm_stats = compute_stats(
        min_days=min_days,
        ic_5d=ic_val,
    )
    new_sm = update_state(sm_stats)
    report["state_machine"] = get_state_summary()

    # ═══════════════════════════════════════════════
    # ㉒ V3 FINAL: 飞书决策卡推送
    # ═══════════════════════════════════════════════
    try:
        from core.feishu_sender import send_decision_card
        ok = send_decision_card(
            system_score=norm_score,
            trend=avg_trend,
            flow=avg_flow,
            value=avg_value,
            decision=decision,
            position=position,
            market_state=market_state,
            state=current_state,
            ic_5d=ic_val,
        )
        step("22_feishu", "ok" if ok else "fail", "pushed" if ok else "send failed")
        if ok:
            print("  📡 飞书推送成功")
    except Exception as e:
        step("22_feishu", "skip", str(e)[:30])
        print(f"  📡 飞书推送跳过: {e}")

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
    print("═" * 60)
    print("  ✅ PIPELINE COMPLETE — V3 FINAL 状态机驱动")
    print("═" * 60)


def _save_log(steps: list, t0: datetime):
    ok_count = sum(1 for s in steps if s["status"] == "ok")
    fail_count = sum(1 for s in steps if s["status"] == "fail")
    elapsed = (now_cn() - t0).total_seconds()

    plog = {
        "pipeline": "v3.0-final",
        "started": t0.isoformat(),
        "elapsed_sec": round(elapsed, 1),
        "total": len(steps),
        "ok_count": ok_count,
        "fail_count": fail_count,
        "steps": steps,
    }
    save_json(plog, "pipeline_log.json")
    print(f"\n  ⏱ 耗时: {elapsed:.0f}s  |  {'✅ 全通过' if fail_count == 0 else f'❌ {fail_count} 失败'}")


def _build_warmup_stats(ranked: list, ic_rpt: dict, bucket_rpt: dict) -> dict:
    """Phase 2 统计摘要: score 分布 + 因子统计 + IC + 分桶"""
    import numpy as np

    stats = {
        "score_count": len(ranked),
        "score_distribution": [],
        "factor_stats": {},
        "top_stocks": [],
        "ic_5d": None,
        "rank_ic_5d": None,
        "signal_count": 0,
        "buckets": [],
    }

    if not ranked:
        return stats

    scores = [r.get("score", 0) for r in ranked]
    trends = [r.get("trend", 0) for r in ranked]
    flows = [r.get("flow", 0) for r in ranked]
    values = [r.get("value", 0) for r in ranked]

    # Score 分布 (4 桶)
    dist_bins = [(0, 3, "0-3"), (3, 6, "3-6"), (6, 9, "6-9"), (9, 999, "9+")]
    for lo, hi, label in dist_bins:
        count = sum(1 for s in scores if lo <= s < hi)
        stats["score_distribution"].append({"bucket": label, "count": count})

    # 因子统计
    for name, vals in [("trend", trends), ("flow", flows), ("value", values)]:
        if vals:
            stats["factor_stats"][name] = {
                "mean": round(float(np.mean(vals)), 1),
                "std": round(float(np.std(vals)), 1),
                "min": round(float(np.min(vals)), 1),
                "max": round(float(np.max(vals)), 1),
            }

    # Top 10
    stats["top_stocks"] = [
        {"code": r["code"], "name": r["name"], "score": r["score"],
         "trend": r.get("trend", 0), "flow": r.get("flow", 0), "value": r.get("value", 0)}
        for r in ranked[:10]
    ]

    # IC 摘要
    ic5 = ic_rpt.get("ic_5d", {})
    ric5 = ic_rpt.get("rank_ic_5d", {})
    stats["ic_5d"] = ic5.get("ic")
    stats["rank_ic_5d"] = ric5.get("rank_ic")
    stats["ic_n"] = ic5.get("n", 0)
    stats["ic_decay"] = ic_rpt.get("ic_decay", {})

    # 信号总数
    try:
        from core.signal_logger import load_history
        stats["signal_count"] = len(load_history())
    except Exception:
        pass

    # 分桶
    stats["buckets"] = bucket_rpt.get("buckets", [])

    return stats


if __name__ == "__main__":
    top = 5
    data_only = False
    for i, arg in enumerate(sys.argv):
        if arg == "--top" and i + 1 < len(sys.argv):
            top = int(sys.argv[i + 1])
        if arg == "--data-only":
            data_only = True
    run_pipeline(top, data_only=data_only)
