"""
pipeline.py — v1→v8 主流程编排器
==================================
严格顺序执行: v1 → v2 → v1.2 → v1.3 → v1.4 → v5 → v6 → v7 → v8 → output
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from src.utils.logger import get_logger
from src.core.context import Context
from src.output.builder import build_output, save_output, save_latest, Result

logger = get_logger("quant.engine.pipeline")


def run(date_str: str = None, data_dir: str = None) -> Result:
    """执行完整 v1-v8 管道, 返回 Result 对象"""
    if date_str is None:
        date_str = config.today_cn()
    if data_dir is None:
        data_dir = config.DATA_DIR
    ctx = Context(date_str, data_dir)
    logger.info("=" * 55)
    logger.info(f"v6 Pipeline 启动: {date_str}")
    logger.info("=" * 55)

    # ── v1: 数据采集 (可插拔数据源) ──
    logger.info("[v1] 数据采集...")

    # 尝试 provider factory (自动选择最佳源)
    try:
        from src.data.provider import get_provider
        provider = get_provider()
        logger.info(f"  数据源: {provider.name}")
    except Exception as e:
        logger.warning(f"Provider 不可用: {e}, 使用直连API")
        provider = None

    # 始终使用直连模块 (保持稳定)
    from src.data.market_data import fetch_index_quotes, compute_market_summary
    from src.data.sector_data import fetch_industry_sectors
    from src.data.stock_data import fetch_stock_quotes
    from src.data.sentiment_data import fetch_hot_stocks, compute_sentiment_indicators
    from src.core.validator import validate_data

    indices = fetch_index_quotes()
    market_summary = compute_market_summary(indices)

    sectors_raw = fetch_industry_sectors()
    stocks_raw = fetch_stock_quotes()

    hot = fetch_hot_stocks(date_str)
    sentiment = compute_sentiment_indicators(stocks_raw, sectors_raw, hot)

    market_status = market_summary.get("market_status", "neutral")

    # ── v2: 板块评分 + 周期 ──
    logger.info("[v2] 板块评分 + 周期...")
    from src.v2.sector_score import score_sectors
    from src.v2.sector_cycle import analyze_cycle

    sectors_scored = score_sectors(sectors_raw)
    cycle_data = analyze_cycle(date_str, data_dir)

    # ── v1.2: 个股评分 ──
    logger.info("[v1.2] 个股评分...")
    from src.v1.stock_score import score_stocks
    from src.core.analyzer import load_history

    history = load_history(data_dir, date_str)
    stocks_scored = score_stocks(stocks_raw, sectors_scored, history.get("stocks"))

    # ── v1.3: 买卖信号 ──
    logger.info("[v1.3] 信号检测...")
    from src.v1.signal_engine import (
        detect_entry_breakout, detect_entry_pullback, detect_entry_sector_start,
        detect_exit_trend_break, detect_exit_climax, detect_exit_weaker,
        compute_indicators,
    )

    # 信号检测仅对高评分个股
    signals = []
    for stock in stocks_scored:
        if stock.get("score", 0) < config.STOCK_SCORE_CANDIDATE:
            continue
        sec = next((s for s in sectors_scored if s["name"] == stock.get("sector", "")), {})
        indicators = compute_indicators(stock, sec)
        entry = (
            detect_entry_breakout(stock, sec, indicators)
            or detect_entry_pullback(stock, sec, indicators)
            or detect_entry_sector_start(stock, sec)
        )
        if entry:
            signals.append({"code": stock["code"], "name": stock["name"], **entry})

    # ── v1.4: 仓位风控 ──
    logger.info("[v1.4] 仓位风控...")
    from src.v4.position import allocate_position, compute_stop_loss, compute_portfolio_risk
    from src.v4.risk_control import trade as compute_trade

    trade_data = compute_trade(date_str, data_dir)

    # ── v5: 市场状态 ──
    logger.info("[v5] 市场状态...")
    from src.v5.market_regime import analyze_regime

    regime_data = analyze_regime(date_str, data_dir)
    regime = regime_data.get("market_regime", "neutral")
    ctx.update_regime(regime, regime_data.get("regime_score", 0))

    # ── v6: 多周期共振 + 自适应权重 ──
    logger.info("[v6] 多周期共振...")
    from src.v6.multi_cycle import analyze_multi_cycle
    from src.v6.resonance import compute_resonance
    from src.v6.adaptive_weights import compute_adaptive_weights

    multi = analyze_multi_cycle(date_str, data_dir)
    resonance = compute_resonance(multi, sectors_raw, stocks_raw)
    adaptive = compute_adaptive_weights(resonance, regime)

    ctx.update_resonance(resonance["overall"]["label"], resonance["overall"]["score"])

    # ── 数据校验 ──
    quality = validate_data(
        {"indices": indices, **market_summary},
        sectors_raw, stocks_raw, sentiment,
    )

    # ── 组装最终输出 ──
    output = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "6.0.0",
        # v1
        "market": {"indices": indices, **market_summary},
        "sectors_raw": sectors_raw[:20],
        "stocks_raw_count": len(stocks_raw),
        "sentiment": sentiment,
        # v2
        "sectors_scored": sectors_scored[:20],
        "cycle_snapshot": cycle_data.get("snapshot", {}),
        # v1.2
        "stocks_scored_count": len(stocks_scored),
        # v1.3
        "signal_count": len(signals),
        # v1.4
        "trade_summary": trade_data.get("summary", {}),
        "portfolio_risk": trade_data.get("portfolio_risk", {}),
        # v5
        "market_regime": regime,
        "regime_label": regime_data.get("regime_label", ""),
        "regime_score": regime_data.get("regime_score", 0),
        "strategy_mode": regime_data.get("strategy_mode", ""),
        # v6
        "resonance": resonance["overall"],
        "adaptive_weights": adaptive,
        # quality
        "data_quality": quality["data_quality"],
        "quality_issues": quality.get("issues", []),
    }

    # ── 落盘 ──
    # 主输出
    out_path = Path(data_dir) / f"{date_str}.json"
    _safe_json_write(out_path, output)

    # 分项输出 (向后兼容)
    _safe_json_write(Path(data_dir) / f"{date_str}_watchlist.json", {
        "date": date_str, "candidates": _top_candidates(stocks_scored),
        "top_sectors": sectors_scored[:20],
    })
    _safe_json_write(Path(data_dir) / f"{date_str}_cycle.json", cycle_data)
    _safe_json_write(Path(data_dir) / f"{date_str}_regime.json", regime_data)
    _safe_json_write(Path(data_dir) / f"{date_str}_trade.json", trade_data)
    _safe_json_write(Path(data_dir) / f"{date_str}_resonance.json", {
        "date": date_str, "resonance": resonance["overall"],
        "adaptive_weights": adaptive, "sector_resonance": resonance.get("sectors", {}),
    })

    ctx.flush()

    logger.info("=" * 55)
    logger.info(f"Pipeline 完成: regime={regime}, resonance={resonance['overall']['label']}, "
                f"quality={quality['data_quality']}")
    logger.info("=" * 55)

    return Result(output)


def _safe_json_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _top_candidates(stocks: list[dict], limit: int = 30) -> list[dict]:
    fields = ["code", "name", "sector", "score", "rank_in_sector", "label",
              "return", "volume_ratio", "relative_strength"]
    ranked = sorted([s for s in stocks if s.get("score", 0) >= config.STOCK_SCORE_CANDIDATE],
                    key=lambda x: x.get("score", 0), reverse=True)
    return [{k: s.get(k) for k in fields if k in s} for s in ranked[:limit]]
