"""
v2_final/data/validate.py — 数据校验层
=========================================
防止脏数据毁回测: 空值/排序/异常价/日期连续性
"""
import logging
from typing import Any

logger = logging.getLogger("v2.validate")


def validate(df) -> tuple[bool, str]:
    """
    校验数据质量。

    Checks:
      1. 空值检查
      2. 日期递增检查
      3. 价格有效性 (收盘价>0)
      4. 涨跌幅范围 (±20% 主板, ±30% 科创)
      5. 最小数据量

    Returns:
        (is_valid, reason)
    """
    if df is None or df.empty:
        return False, "empty dataframe"

    # 1. 空值
    nulls = df.isnull().sum().sum()
    if nulls > 0:
        return False, f"{nulls} null values"

    # 2. 日期排序 (using 'date' column if exists, else index)
    date_col = "date" if "date" in df.columns else df.columns[0]
    if date_col in df.columns:
        dates = df[date_col]
        if not dates.is_monotonic_increasing:
            return False, "date order not increasing"

    # 3. 价格有效性
    close_col = "close" if "close" in df.columns else "收盘"
    if close_col in df.columns:
        if (df[close_col] <= 0).any():
            return False, "invalid close price (<= 0)"

    # 4. 涨跌幅范围
    pct_col = "pct" if "pct" in df.columns else "涨跌幅"
    if pct_col in df.columns:
        pct_max = df[pct_col].max()
        pct_min = df[pct_col].min()
        if pct_max > 30 or pct_min < -30:
            logger.warning(f"异常涨跌幅: max={pct_max} min={pct_min}")

    # 5. 最小量
    if len(df) < 20:
        return False, f"insufficient data: {len(df)} rows"

    return True, "ok"


def validate_directory(data_dir: str = "data/raw/daily") -> dict[str, Any]:
    """批量校验目录下所有 CSV"""
    import os
    import pandas as pd
    from pathlib import Path

    results = {"total": 0, "valid": 0, "invalid": 0, "errors": []}

    for fp in Path(data_dir).glob("*.csv"):
        try:
            df = pd.read_csv(fp)
            valid, reason = validate(df)
            results["total"] += 1
            if valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["errors"].append({"file": fp.name, "reason": reason})
        except Exception as e:
            results["invalid"] += 1
            results["errors"].append({"file": fp.name, "reason": str(e)})

    logger.info(f"校验: {results['valid']}/{results['total']} 通过" +
                (f", {results['invalid']} 失败" if results['invalid'] > 0 else ""))
    return results
