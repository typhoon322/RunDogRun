"""
validator.py — 数据校验 + 质量标记 + 异常过滤
==============================================
每次输出必须经过校验，确保数据可靠性
"""

import logging
from typing import Any

import config

logger = logging.getLogger("quant-collector.validator")


def validate_data(
    market_data: dict[str, Any],
    sectors: list[dict[str, Any]],
    stocks: list[dict[str, Any]],
    sentiment: dict[str, Any],
) -> dict[str, Any]:
    """
    全面数据校验，返回质量报告。

    Returns:
        {data_quality, issues, metrics}
          data_quality: "ok" | "warning" | "error"
    """
    issues = []
    metrics = {}

    # 1. 大盘数据完整性
    _check_market(market_data, issues, metrics)

    # 2. 板块数据完整性
    _check_sectors(sectors, issues, metrics)

    # 3. 个股数据完整性
    _check_stocks(stocks, issues, metrics)

    # 4. 异常波动检查
    _check_extreme_moves(market_data, stocks, issues)

    # 5. 数据一致性
    _check_consistency(market_data, stocks, sentiment, issues)

    # 确定质量等级
    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")

    if error_count > 0:
        data_quality = "error"
    elif warning_count > 0:
        data_quality = "warning"
    else:
        data_quality = "ok"

    logger.info(
        f"数据校验: quality={data_quality}, errors={error_count}, warnings={warning_count}"
    )

    return {
        "data_quality": data_quality,
        "issues": issues,
        "metrics": metrics,
    }


def _check_market(
    market_data: dict, issues: list, metrics: dict
) -> None:
    """检查大盘数据"""
    indices = market_data.get("indices", [])
    expected = len(config.INDEX_LIST)
    actual = len(indices)

    metrics["market_indices_expected"] = expected
    metrics["market_indices_actual"] = actual

    if actual == 0:
        issues.append({
            "severity": "error",
            "field": "market.indices",
            "message": f"大盘指数数据完全缺失 (期望 {expected} 个)",
        })
    elif actual < expected * 0.8:
        missing_ratio = (expected - actual) / expected
        issues.append({
            "severity": "warning",
            "field": "market.indices",
            "message": (
                f"大盘指数数据缺失 {expected - actual}/{expected} "
                f"({missing_ratio:.0%})"
            ),
        })

    # 检查涨跌幅是否合理
    for idx in indices:
        if abs(idx.get("change_pct", 0)) > config.QUALITY_EXTREME_INDEX_CHANGE:
            issues.append({
                "severity": "warning",
                "field": f"market.{idx.get('code')}.change_pct",
                "message": (
                    f"指数 {idx.get('name')} 涨跌幅 {idx['change_pct']}% "
                    f"超过阈值 ±{config.QUALITY_EXTREME_INDEX_CHANGE}%"
                ),
            })


def _check_sectors(
    sectors: list, issues: list, metrics: dict
) -> None:
    """检查板块数据"""
    expected_min = 50  # 东财行业板块至少50个
    actual = len(sectors)

    metrics["sectors_expected_min"] = expected_min
    metrics["sectors_actual"] = actual

    if actual == 0:
        issues.append({
            "severity": "warning",
            "field": "sectors",
            "message": "板块数据完全缺失 (东财接口可能失败)",
        })
    elif actual < expected_min * 0.5:
        issues.append({
            "severity": "warning",
            "field": "sectors",
            "message": f"板块数据不足: {actual} < {expected_min}",
        })


def _check_stocks(
    stocks: list, issues: list, metrics: dict
) -> None:
    """检查个股数据"""
    total = len(stocks)
    active = sum(1 for s in stocks if not s.get("is_suspended"))
    suspended = sum(1 for s in stocks if s.get("is_suspended"))
    missing = sum(1 for s in stocks if s.get("is_suspended") and s.get("price") == 0)

    metrics["stocks_total"] = total
    metrics["stocks_active"] = active
    metrics["stocks_suspended"] = suspended
    metrics["stocks_missing_data"] = missing

    if total == 0:
        issues.append({
            "severity": "error",
            "field": "stocks",
            "message": "个股数据完全缺失",
        })
        return

    missing_ratio = missing / total if total > 0 else 0
    metrics["stocks_missing_ratio"] = round(missing_ratio, 3)

    if missing_ratio > config.QUALITY_MAX_MISSING_RATIO:
        issues.append({
            "severity": "warning",
            "field": "stocks",
            "message": (
                f"个股数据缺失率 {missing_ratio:.1%} "
                f"超过阈值 {config.QUALITY_MAX_MISSING_RATIO:.0%}"
            ),
        })

    # 检查是否有异常集中的涨跌
    extreme_up = sum(
        1 for s in stocks
        if s.get("return", 0) > config.QUALITY_EXTREME_STOCK_CHANGE
    )
    extreme_down = sum(
        1 for s in stocks
        if s.get("return", 0) < -config.QUALITY_EXTREME_STOCK_CHANGE
    )
    metrics["stocks_extreme_up"] = extreme_up
    metrics["stocks_extreme_down"] = extreme_down


def _check_extreme_moves(
    market_data: dict, stocks: list, issues: list
) -> None:
    """检查极端行情"""
    limit_up = sum(1 for s in stocks if s.get("is_limit_up"))
    limit_down = sum(1 for s in stocks if s.get("is_limit_down"))

    # 百股涨停/跌停标注
    if limit_up >= 200:
        issues.append({
            "severity": "info",
            "field": "sentiment",
            "message": f"大面积涨停 ({limit_up}只), 市场极端乐观",
        })
    if limit_down >= 200:
        issues.append({
            "severity": "warning",
            "field": "sentiment",
            "message": f"大面积跌停 ({limit_down}只), 可能存在系统性风险",
        })


def _check_consistency(
    market_data: dict,
    stocks: list,
    sentiment: dict,
    issues: list,
) -> None:
    """检查数据一致性"""
    # 涨跌停数与情绪指标一致性
    stock_limit_up = sum(1 for s in stocks if s.get("is_limit_up"))
    stock_limit_down = sum(1 for s in stocks if s.get("is_limit_down"))

    sentiment_up = sentiment.get("limit_up_count", 0)
    sentiment_down = sentiment.get("limit_down_count", 0)

    if abs(stock_limit_up - sentiment_up) > stock_limit_up * 0.5:
        issues.append({
            "severity": "warning",
            "field": "consistency",
            "message": (
                f"涨停数不一致: 个股统计={stock_limit_up}, 情绪统计={sentiment_up}"
            ),
        })
