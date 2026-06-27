"""
trade_engine.py — 交易编排引擎 (v1.3 + v1.4)
===============================================
状态机: OBSERVE → ENTRY → HOLD → EXIT

流程:
  1. 读取上次持仓状态 (data/positions.json)
  2. 读取当日原始数据 + 评分数据
  3. 对持仓股: 检测是否触发 EXIT
  4. 对候选股: 检测是否触发 ENTRY
  5. 分配仓位 + 风控
  6. 输出执行建议
  7. 更新 positions.json
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from src.v1_3_signal.entry_exit import (
    compute_indicators,
    detect_entry_breakout,
    detect_entry_pullback,
    detect_entry_sector_start,
    detect_exit_trend_break,
    detect_exit_climax,
    detect_exit_weaker,
)
from src.position import (
    allocate_position,
    compute_stop_loss,
    compute_portfolio_risk,
)

logger = logging.getLogger("quant-collector.trade-engine")


def load_positions(data_dir: str) -> dict[str, Any]:
    """读取上次持仓状态文件"""
    path = Path(data_dir) / "positions.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"holdings": {}, "date": None}


def save_positions(data_dir: str, state: dict[str, Any]) -> None:
    """持久化持仓状态"""
    path = Path(data_dir) / "positions.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_price_history(
    data_dir: str,
    target_date: str,
    lookback: int = config.HISTORY_LOOKBACK_DAYS,
) -> dict[str, list[dict[str, Any]]]:
    """
    加载个股多日价格历史 (用于MA/前高计算)。

    Returns:
        {stock_code: [{price, high, low, volume_ratio, return}, ...]} 按日期升序
    """
    hist: dict[str, list] = defaultdict(list)
    from datetime import datetime as dt, timedelta

    target_dt = dt.strptime(target_date, "%Y-%m-%d")

    for day_offset in range(lookback, 0, -1):
        check_dt = target_dt - timedelta(days=day_offset)
        check_date = check_dt.strftime("%Y-%m-%d")
        filepath = Path(data_dir) / f"{check_date}.json"
        if not filepath.exists():
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("data_quality") == "failed":
            continue

        for s in data.get("stocks", []):
            code = s.get("code", "")
            hist[code].append({
                "price": s.get("price", 0),
                "high": s.get("high", 0),
                "low": s.get("low", 0),
                "volume_ratio": s.get("volume_ratio", 1.0),
                "return": s.get("return", 0),
            })

    return dict(hist)


def load_prev_day_sectors(data_dir: str, target_date: str) -> dict[str, Any]:
    """加载上一交易日板块数据 (用于晋级判断)"""
    from datetime import datetime as dt, timedelta

    target_dt = dt.strptime(target_date, "%Y-%m-%d")
    for offset in range(1, 8):  # 向前找7天
        check_dt = target_dt - timedelta(days=offset)
        check_date = check_dt.strftime("%Y-%m-%d")
        filepath = Path(data_dir) / f"{check_date}.json"
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
    return {"sectors": []}


def trade(date_str: str, data_dir: str = config.DATA_DIR) -> dict[str, Any]:
    """
    完整交易分析流程。

    Args:
        date_str: 分析日期
        data_dir: 数据目录

    Returns:
        执行建议 JSON
    """
    # 1. 读取当日数据
    data_path = Path(data_dir) / f"{date_str}.json"
    watchlist_path = Path(data_dir) / f"{date_str}_watchlist.json"

    if not data_path.exists():
        logger.error(f"当日数据不存在: {data_path}")
        return _empty_result(date_str, "data_not_found")

    with open(data_path, encoding="utf-8") as f:
        today_data = json.load(f)

    # 2. 读取 watchlist (候选池)
    candidates_lookup: dict[str, dict] = {}
    if watchlist_path.exists():
        with open(watchlist_path, encoding="utf-8") as f:
            watchlist = json.load(f)
        # 构建: sector_scores + candidates
        for c in watchlist.get("candidates", []):
            candidates_lookup[c["code"]] = c

    # 3. 读取板块评分 (从 watchlist 的 top_sectors)
    sector_scores: dict[str, Any] = {}
    if watchlist_path.exists():
        for s in watchlist.get("top_sectors", []):
            sector_scores[s["name"]] = s

    # 4. 加载历史价格 + 上一日板块数据
    price_hist = load_price_history(data_dir, date_str)
    prev_data = load_prev_day_sectors(data_dir, date_str)
    prev_sectors_raw = prev_data.get("sectors", [])
    prev_sector_lookup = {s["name"]: s for s in prev_sectors_raw}

    # 5. 加载上次持仓状态
    pos_state = load_positions(data_dir)

    # 6. 当前持仓信号检测 (EXIT)
    holdings = pos_state.get("holdings", {})
    positions: list[dict[str, Any]] = []
    exited_codes: set[str] = set()

    for code, holding in holdings.items():
        stock = _find_stock(today_data, code)
        if not stock:
            continue

        sec_name = stock.get("sector", "")
        sec = sector_scores.get(sec_name, {})

        # 注入score(从candidates)
        candidate = candidates_lookup.get(code, {})
        stock["score"] = candidate.get("score", 0)
        stock["relative_strength"] = candidate.get("relative_strength", 0)
        stock["rank_in_sector"] = candidate.get("rank_in_sector", 99)

        indicators = compute_indicators(stock, sec, price_hist.get(code))

        # 检测卖出信号
        sell_signal = (
            detect_exit_trend_break(stock, sec, indicators)
            or detect_exit_climax(stock, sec, holding.get("entry_sector_score", 0))
            or detect_exit_weaker(stock, sec)
        )

        if sell_signal:
            stock.update(sell_signal)
            stock["state"] = "EXIT"
            stock["position_size"] = 0
            stock["stop_loss"] = "—"
            positions.append(stock)
            exited_codes.add(code)
        else:
            # 持仓中
            stock["state"] = "HOLD"
            stock["action"] = "HOLD"
            stock["signal_type"] = "continue"
            stock["signal_grade"] = "—"
            stock["position_size"] = holding.get("position_size", 0)
            stock["stop_loss"] = holding.get("stop_loss", "—")
            stock["confidence"] = holding.get("confidence", 0.7)
            positions.append(stock)

    # 7. 候选股信号检测 (ENTRY)
    sector_exposure = _compute_sector_exposure(positions)
    current_count = len(positions) - len(exited_codes)

    # 收集所有候选 (来自 watchlist)
    candidates = candidates_lookup

    for code, candidate in candidates.items():
        if code in holdings and code not in exited_codes:
            continue  # 已持有且未退出

        stock = _find_stock(today_data, code)
        if not stock:
            continue

        # 注入score
        stock["score"] = candidate.get("score", 0)
        stock["relative_strength"] = candidate.get("relative_strength", 0)
        stock["rank_in_sector"] = candidate.get("rank_in_sector", 99)

        sec_name = stock.get("sector", "")
        sec = sector_scores.get(sec_name, {})

        indicators = compute_indicators(stock, sec, price_hist.get(code))

        # 板块 Breadth 变化 (用于C类)
        prev_sec = prev_sector_lookup.get(sec_name, {})
        prev_total = prev_sec.get("total_stocks", 1)
        prev_breadth = prev_sec.get("up_count", 0) / max(1, prev_total)
        cur_total = sec.get("total_stocks", len(candidates) + 1)
        cur_breadth = sec.get("up_count", 0) / max(1, cur_total) if sec else 0

        # 检测买入信号 (优先级 A > B > C)
        entry_signal = (
            detect_entry_breakout(stock, sec, indicators)
            or detect_entry_pullback(stock, sec, indicators)
            or detect_entry_sector_start(stock, sec, cur_breadth, prev_breadth)
        )

        if entry_signal:
            sec_exp = sector_exposure.get(sec_name, 0)
            pos_size = allocate_position(entry_signal, sec_exp, current_count)

            if pos_size > 0:
                stock.update(entry_signal)
                stock["position_size"] = pos_size
                stock["stop_loss"] = compute_stop_loss(
                    entry_signal["signal_grade"], stock
                )
                stock["state"] = "ENTRY"
                positions.append(stock)
                sector_exposure[sec_name] = sec_exp + pos_size
                current_count += 1
            else:
                # 仓位分配失败
                stock.update(entry_signal)
                stock["position_size"] = 0
                stock["stop_loss"] = "—"
                stock["state"] = "OBSERVE"
                stock["action"] = "OBSERVE"
                positions.append(stock)

    # 8. 组合风控
    portfolio_risk = compute_portfolio_risk(
        positions,
        today_data.get("sentiment", {}),
    )

    # 9. 更新持仓状态 (仅保存 BUY/HOLD 的)
    new_holdings = {}
    for p in positions:
        if p.get("state") in ("ENTRY", "HOLD") and p.get("position_size", 0) > 0:
            new_holdings[p["code"]] = {
                "name": p.get("name", ""),
                "sector": p.get("sector", ""),
                "position_size": p.get("position_size", 0),
                "entry_date": (
                    holdings.get(p["code"], {}).get("entry_date", date_str)
                    if p["state"] == "HOLD"
                    else date_str
                ),
                "entry_price": p.get("price", 0),
                "entry_sector_score": sector_scores.get(
                    p.get("sector", ""), {}
                ).get("score", 0),
                "stop_loss": p.get("stop_loss", "—"),
                "confidence": p.get("confidence", 0),
            }

    save_positions(data_dir, {
        "holdings": new_holdings,
        "date": date_str,
    })

    # 10. 组装输出
    entry_count = sum(1 for p in positions if p.get("state") == "ENTRY")
    hold_count = sum(1 for p in positions if p.get("state") == "HOLD")
    exit_count = sum(1 for p in positions if p.get("state") == "EXIT")

    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "1.4.0",
        "positions": _format_positions(positions),
        "portfolio_risk": portfolio_risk,
        "summary": {
            "total_signals": len(positions),
            "entry_count": entry_count,
            "hold_count": hold_count,
            "exit_count": exit_count,
        },
    }

    logger.info(
        f"交易分析完成: BUY{entry_count} HOLD{hold_count} SELL{exit_count}"
    )
    return result


def _find_stock(data: dict, code: str) -> dict[str, Any] | None:
    for s in data.get("stocks", []):
        if s["code"] == code:
            return s
    return None


def _compute_sector_exposure(positions: list[dict]) -> dict[str, float]:
    exp: dict[str, float] = defaultdict(float)
    for p in positions:
        if p.get("state") != "EXIT":
            exp[p.get("sector", "")] += p.get("position_size", 0)
    return dict(exp)


def _format_positions(positions: list[dict]) -> list[dict]:
    """精简输出字段"""
    key_fields = [
        "code", "name", "sector",
        "action", "signal_type", "signal_grade",
        "position_size", "risk_level", "stop_loss",
        "confidence", "state", "price", "return",
        "reason",
    ]
    return [
        {k: p.get(k) for k in key_fields if k in p}
        for p in positions
    ]


def _empty_result(date_str: str, reason: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "1.4.0",
        "error": reason,
        "positions": [],
        "portfolio_risk": {
            "total_exposure": 0.0,
            "max_sector_exposure": 0.0,
            "position_count": 0,
            "risk_state": "unknown",
        },
        "summary": {"total_signals": 0, "entry_count": 0, "hold_count": 0, "exit_count": 0},
    }
