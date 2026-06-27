"""
analyzer.py — 双层评分编排器 (v1.1 + v1.2)
============================================
职责:
  1. 读取 data/ 目录历史数据
  2. 调用 Layer 1: 板块评分
  3. 调用 Layer 2: 个股评分
  4. 生成候选交易池
  5. 输出标准化 watchlist JSON
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config
from src.v2_sector.sector_score import score_sectors
from src.v1_2_stock.stock_score import score_stocks

logger = logging.getLogger("quant-collector.analyzer")


def load_history(
    data_dir: str,
    target_date: str,
    lookback: int = config.HISTORY_LOOKBACK_DAYS,
) -> dict[str, dict[str, Any]]:
    """
    加载历史数据。

    Returns:
        {
            "sectors": {sector_name: [历史数据列表]},
            "stocks": {sector_name: {stock_code: [历史数据列表]}},
        }
    """
    hist_sectors: dict[str, list] = defaultdict(list)
    hist_stocks: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    loaded = 0

    for day_offset in range(lookback, 0, -1):
        check_dt = target_dt - timedelta(days=day_offset)
        check_date = check_dt.strftime("%Y-%m-%d")
        filepath = Path(data_dir) / f"{check_date}.json"

        if not filepath.exists():
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取历史文件失败 {check_date}: {e}")
            continue

        if data.get("data_quality") == "failed":
            logger.warning(f"历史数据 {check_date} 质量=failed, 跳过")
            continue

        # 累积板块历史
        for sector in data.get("sectors", []):
            name = sector.get("name", "")
            hist_sectors[name].append(sector)

        # 累积个股历史 (按 sector→stock 两级)
        for stock in data.get("stocks", []):
            sec_name = stock.get("sector", "")
            code = stock.get("code", "")
            hist_stocks[sec_name][code].append(stock)

        loaded += 1

    logger.info(f"历史数据: 加载 {loaded}/{lookback} 天")
    return {
        "sectors": dict(hist_sectors),
        "stocks": {s: dict(codes) for s, codes in hist_stocks.items()},
    }


def analyze(
    date_str: str,
    data_dir: str = config.DATA_DIR,
) -> dict[str, Any]:
    """
    完整分析流程: 读当日数据 → 加载历史 → 双层评分 → 候选池

    Args:
        date_str: 分析日期 YYYY-MM-DD
        data_dir: 数据目录

    Returns:
        标准化 watchlist JSON
    """
    # 1. 读取当日数据
    filepath = Path(data_dir) / f"{date_str}.json"
    if not filepath.exists():
        logger.error(f"当日数据不存在: {filepath}")
        return _empty_result(date_str, "data_not_found")

    with open(filepath, encoding="utf-8") as f:
        today_data = json.load(f)

    sectors_today = today_data.get("sectors", [])
    stocks_today = today_data.get("stocks", [])

    if not sectors_today or not stocks_today:
        logger.error("当日数据为空")
        return _empty_result(date_str, "empty_data")

    # 2. 加载历史
    history = load_history(data_dir, date_str)

    # 3. Layer 1: 板块评分
    logger.info(f"Layer 1: 板块评分 ({len(sectors_today)} 个板块)")
    sector_scored = score_sectors(sectors_today, history.get("sectors"))

    # 4. Layer 2: 个股评分
    logger.info(f"Layer 2: 个股评分 ({len(stocks_today)} 只)")
    stock_scored = score_stocks(stocks_today, sector_scored, history.get("stocks"))

    # 5. 候选池生成
    candidates = _generate_candidates(sector_scored, stock_scored)

    # 6. 组装输出
    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "1.2.0",
        "top_sectors": _top_sectors(sector_scored),
        "candidates": _top_candidates(candidates),
        "snapshot": {
            "total_sectors": len(sector_scored),
            "qualified_sectors": sum(
                1 for s in sector_scored
                if s["score"] >= config.SECTOR_SCORE_QUALIFIED
            ),
            "core_trend_sectors": sum(
                1 for s in sector_scored
                if s["label"] == "core_trend"
            ),
            "total_stocks": len(stock_scored),
            "candidate_count": len(candidates),
            "leading_count": sum(
                1 for c in candidates if c["label"] == "leading_stock"
            ),
            "market_status": today_data.get("market", {}).get("market_status", "unknown"),
        },
    }

    qualified_count = sum(
        1 for s in sector_scored
        if s["score"] >= config.SECTOR_SCORE_QUALIFIED
    )
    logger.info(
        f"分析完成: 板块{qualified_count}/{len(sector_scored)}达标, "
        f"候选{len(candidates)}只"
    )
    return result


def _generate_candidates(
    sectors: list[dict[str, Any]],
    stocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    生成候选交易池:
      1. 筛选 Sector Score ≥ 6 的板块
      2. 筛选这些板块中 Stock Score ≥ 7 的个股
      3. 每个板块保留 Top 3
    """
    # 板块达标集合
    qualified_sectors = {
        s["name"]: s
        for s in sectors
        if s["score"] >= config.SECTOR_SCORE_QUALIFIED
    }

    # 筛选个股
    candidates = []
    for stock in stocks:
        sec = stock.get("sector", "")
        if sec not in qualified_sectors:
            continue
        if stock.get("score", 0) < config.STOCK_SCORE_CANDIDATE:
            continue
        candidates.append(stock)

    # 板块内排序 + top N
    from collections import defaultdict
    by_sector = defaultdict(list)
    for c in candidates:
        by_sector[c["sector"]].append(c)

    top_candidates = []
    for sec_name, sec_stocks in by_sector.items():
        sec_stocks.sort(key=lambda x: x["score"], reverse=True)
        top_candidates.extend(sec_stocks[:config.CANDIDATES_PER_SECTOR])

    # 全局排序
    top_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 总量控制
    return top_candidates[:config.MAX_CANDIDATES_TOTAL]


def _top_sectors(sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """提取 top sectors (score ≥ 4, 最多20个)"""
    return [
        s for s in sectors
        if s["score"] >= 4
    ][:20]


def _top_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """精简候选池输出"""
    fields = [
        "sector", "code", "name", "score", "rank_in_sector",
        "label", "return", "volume_ratio",
        "trend", "relative_strength", "volume", "structure", "timing",
    ]
    return [
        {k: c.get(k) for k in fields if k in c}
        for c in candidates
    ]


def _empty_result(date_str: str, reason: str) -> dict[str, Any]:
    """生成空结果"""
    return {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "1.2.0",
        "error": reason,
        "top_sectors": [],
        "candidates": [],
        "snapshot": {},
    }
