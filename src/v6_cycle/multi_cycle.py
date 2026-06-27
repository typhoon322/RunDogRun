"""
multi_cycle.py — v6 多周期分析 (日/周/月)
===========================================
从 data/*.json 历史聚合出 D/W/M 三级指标
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v6.multi_cycle")


def analyze_multi_cycle(
    date_str: str,
    data_dir: str = "data",
    lookback: int = 30,
) -> dict[str, Any]:
    """
    对每个板块/个股计算 日/周/月 三级指标。

    Returns:
        {sectors: {name: {daily, weekly, monthly}}, stocks: {code: {daily, weekly, monthly}}}
    """
    target_dt = datetime.strptime(date_str, "%Y-%m-%d")
    daily_hist, weekly_hist, monthly_hist = _collect_history(data_dir, target_dt, lookback)

    sectors = _aggregate_sectors(daily_hist, weekly_hist, monthly_hist)
    stocks = _aggregate_stocks(daily_hist, weekly_hist, monthly_hist)

    logger.info(f"多周期: {len(sectors)}板块, {len(stocks)}个股")
    return {"sectors": sectors, "stocks": stocks}


def _collect_history(data_dir: str, target_dt: datetime, lookback: int):
    """收集 日/周/月 历史数据"""
    daily: list[dict] = []
    weekly: list[dict] = []   # 按周聚合
    monthly: list[dict] = []  # 按月聚合

    current_week = None
    current_month = None
    week_bucket: dict[str, list] = defaultdict(list)
    month_bucket: dict[str, list] = defaultdict(list)

    for offset in range(lookback, 0, -1):
        dt = target_dt - timedelta(days=offset)
        date_s = dt.strftime("%Y-%m-%d")
        fp = Path(data_dir) / f"{date_s}.json"
        if not fp.exists():
            continue
        try:
            with open(fp) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        daily.append({"date": date_s, "data": data})

        # 周聚合
        iso = dt.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        week_bucket[week_key].append(data)

        # 月聚合
        month_key = dt.strftime("%Y-%m")
        month_bucket[month_key].append(data)

    # 构建周级 (每周汇总)
    for wk, items in week_bucket.items():
        agg = _aggregate_period(items)
        agg["period"] = wk
        weekly.append(agg)

    # 构建月级
    for mo, items in month_bucket.items():
        agg = _aggregate_period(items)
        agg["period"] = mo
        monthly.append(agg)

    return daily, weekly, monthly


def _aggregate_period(items: list[dict]) -> dict:
    """聚合一个时间段的数据"""
    if not items:
        return {}
    sector_changes: dict[str, list] = defaultdict(list)
    stock_changes: dict[str, list] = defaultdict(list)

    for item in items:
        for sec in item.get("sectors", []):
            sector_changes[sec.get("name", "")].append(sec.get("change_pct", 0))
        for stk in item.get("stocks", []):
            stock_changes[stk.get("code", "")].append(stk.get("return", 0))

    return {
        "sector_avg": {k: sum(v)/len(v) for k, v in sector_changes.items()},
        "stock_avg": {k: sum(v)/len(v) for k, v in stock_changes.items()},
    }


def _aggregate_sectors(daily: list, weekly: list, monthly: list) -> dict[str, dict]:
    """板块级日/周/月指标"""
    result: dict[str, dict] = defaultdict(lambda: {"daily": {}, "weekly": {}, "monthly": {}})

    # 日级: 取最新一天
    if daily:
        last = daily[-1]["data"]
        for sec in last.get("sectors", []):
            n = sec.get("name", "")
            result[n]["daily"] = {
                "change_pct": sec.get("change_pct", 0),
                "strength_score": sec.get("strength_score", 0),
                "money_flow": sec.get("money_flow", ""),
                "up_count": sec.get("up_count", 0),
                "total": sec.get("total_stocks", 0),
            }

    # 周级: 最近一周
    if weekly:
        for sec_name, avg in weekly[-1].get("sector_avg", {}).items():
            result[sec_name]["weekly"] = {"period": weekly[-1]["period"], "avg_change": round(avg, 2)}

    # 月级: 最近一月
    if monthly:
        for sec_name, avg in monthly[-1].get("sector_avg", {}).items():
            result[sec_name]["monthly"] = {"period": monthly[-1]["period"], "avg_change": round(avg, 2)}

    return dict(result)


def _aggregate_stocks(daily: list, weekly: list, monthly: list) -> dict[str, dict]:
    """个股级日/周/月指标"""
    result: dict[str, dict] = defaultdict(lambda: {"daily": {}, "weekly": {}, "monthly": {}})

    if daily:
        last = daily[-1]["data"]
        for stk in last.get("stocks", []):
            code = stk.get("code", "")
            result[code]["daily"] = {
                "return": stk.get("return", 0),
                "volume_ratio": stk.get("volume_ratio", 0),
                "price": stk.get("price", 0),
            }

    if weekly:
        for code, avg in weekly[-1].get("stock_avg", {}).items():
            result[code]["weekly"] = {"avg_return": round(avg, 2)}

    if monthly:
        for code, avg in monthly[-1].get("stock_avg", {}).items():
            result[code]["monthly"] = {"avg_return": round(avg, 2)}

    return dict(result)
