"""
core/data_consistency.py — v2.7 数据-策略一致性校验
=======================================================
三重防线: CSV完整性 / Universe对齐 / 回测数据断层检测
"""
import logging
import os
from typing import Any

logger = logging.getLogger("v2.consistency")

DATA_DIR = "data/raw/daily"


def check_csv_integrity(data_dir: str = DATA_DIR) -> dict[str, Any]:
    """
    CSV 文件完整性检查。
    """
    if not os.path.exists(data_dir):
        return {"total": 0, "bad": [], "error": "directory not found"}

    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    bad = []

    for f in files:
        path = os.path.join(data_dir, f)
        try:
            import pandas as pd
            df = pd.read_csv(path)
            if len(df) < 100:
                bad.append(f"{f} (only {len(df)} rows)")
            if "close" not in df.columns and "收盘" not in df.columns:
                bad.append(f"{f} (missing close column)")
        except Exception as e:
            bad.append(f"{f} ({e})")

    ok = len(files) - len(bad)
    logger.info(f"CSV检查: {ok}/{len(files)} OK" +
                (f", {len(bad)} BAD" if bad else ""))
    return {"total": len(files), "ok": ok, "bad": bad, "bad_count": len(bad)}


def check_universe_alignment(universe: list[str], data_dir: str = DATA_DIR) -> dict[str, Any]:
    """
    Universe vs 数据仓库 对齐检查。
    返回: 缺失列表, 对齐率
    """
    if not os.path.exists(data_dir):
        return {"align_pct": 0, "missing": universe, "error": "data directory not found"}

    existing = set(f.replace(".csv", "") for f in os.listdir(data_dir) if f.endswith(".csv"))
    missing = [c for c in universe if c not in existing]

    align_pct = round((len(universe) - len(missing)) / max(1, len(universe)) * 100, 1)

    if missing:
        logger.warning(f"Universe对齐: {align_pct}%, 缺失 {len(missing)} 只")
    else:
        logger.info(f"Universe对齐: 100% ({len(universe)} 只)")

    return {
        "universe_size": len(universe),
        "data_size": len(existing),
        "missing": missing[:10],
        "missing_count": len(missing),
        "align_pct": align_pct,
    }


def check_backtest_data(
    portfolio: list[dict],
    price_data: dict[str, list[float]],
) -> dict[str, Any]:
    """
    回测数据断层检测: 是否有股票无数据/数据不足。
    """
    gaps = []
    for p in portfolio:
        code = p["code"]
        prices = price_data.get(code, [])
        if not prices:
            gaps.append({"code": code, "name": p.get("name", ""), "issue": "无数据"})
        elif len(prices) < 30:
            gaps.append({"code": code, "name": p.get("name", ""),
                         "issue": f"仅{len(prices)}天"})

    return {
        "portfolio_size": len(portfolio),
        "gaps": gaps,
        "gap_count": len(gaps),
        "healthy": len(portfolio) - len(gaps),
    }
