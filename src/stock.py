"""
stock.py — 个股涨跌与量能数据采集 (腾讯财经批量)
==================================================
数据源: 腾讯财经 qt.gtimg.cn (批量, 不封IP)
特点: 一次请求最多约50只股票, 分批次调用
"""

import logging
from typing import Any

import requests

import config
from src.utils import safe_float, retry_request, chunk_list

logger = logging.getLogger("quant-collector.stock")


def _build_tencent_codes(codes: list[str]) -> list[str]:
    """构造腾讯财经代码前缀"""
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    return prefixed


def _parse_tencent_line(line: str) -> dict[str, Any] | None:
    """
    解析腾讯财经单行数据 (~分隔, 88字段)

    关键字段:
      1=名称, 3=当前价, 4=昨收, 5=今开, 31=涨跌额, 32=涨跌幅%,
      33=最高, 34=最低, 37=成交额(万), 38=换手率%,
      39=PE(TTM), 44=总市值(亿), 45=流通市值(亿), 46=PB,
      47=涨停价, 48=跌停价, 49=量比, 52=PE(静)
    """
    if "=" not in line or '"' not in line:
        return None

    try:
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            return None

        code = key[2:]
        return {
            "code": code,
            "name": vals[1],
            "price": safe_float(vals[3]),
            "last_close": safe_float(vals[4]),
            "open": safe_float(vals[5]),
            "high": safe_float(vals[33]),
            "low": safe_float(vals[34]),
            "change_pct": round(safe_float(vals[32]), 2),
            "change_amt": safe_float(vals[31]),
            "amount_wan": safe_float(vals[37]),
            "turnover_pct": safe_float(vals[38]),
            "pe_ttm": safe_float(vals[39]),
            "pb": safe_float(vals[46]),
            "mcap_yi": safe_float(vals[44]),
            "float_mcap_yi": safe_float(vals[45]),
            "volume_ratio": safe_float(vals[49]),
            "limit_up": safe_float(vals[47]),
            "limit_down": safe_float(vals[48]),
            "pe_static": safe_float(vals[52]),
        }
    except (IndexError, ValueError) as e:
        logger.warning(f"解析个股数据行失败: {e}")
        return None


def _fetch_batch(codes: list[str], retries: int = 2) -> dict[str, dict[str, Any]]:
    """拉取一批股票的行情数据"""
    prefixed = _build_tencent_codes(codes)
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)

    def _request():
        headers = {"User-Agent": "Mozilla/5.0"}
        return requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)

    resp = retry_request(lambda: _request(), label="stock/tencent", max_retries=retries)
    if resp is None:
        return {}

    resp.encoding = "gbk"
    data = resp.text

    results = {}
    for line in data.strip().split(";"):
        parsed = _parse_tencent_line(line)
        if parsed:
            results[parsed["code"]] = parsed

    return results


def fetch_stock_quotes(
    stock_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    批量获取个股行情数据

    Args:
        stock_codes: 股票代码列表，默认使用 config.STOCK_POOL

    Returns:
        [{code, name, return(=change_pct), price, volume_ratio,
          turnover_pct, pe_ttm, pb, mcap_yi, trend_score,
          is_limit_up, is_limit_down, is_st, is_suspended}, ...]
    """
    if stock_codes is None:
        stock_codes = config.STOCK_POOL

    batches = chunk_list(stock_codes, config.TENCENT_BATCH_SIZE)
    all_stocks: dict[str, dict[str, Any]] = {}

    for i, batch in enumerate(batches):
        logger.info(f"个股行情: 批次 {i+1}/{len(batches)} ({len(batch)}只)")
        batch_data = _fetch_batch(batch)
        all_stocks.update(batch_data)

    # 转换为标准输出格式
    results = []
    for code in stock_codes:
        raw = all_stocks.get(code)
        if raw is None:
            # 数据缺失
            results.append({
                "code": code,
                "sector": config.STOCK_SECTOR_MAP.get(code, ""),
                "name": config.STOCK_NAMES.get(code, f"股票{code}"),
                "return": 0.0,
                "price": 0.0,
                "volume_ratio": 0.0,
                "turnover_pct": 0.0,
                "pe_ttm": 0.0,
                "pb": 0.0,
                "mcap_yi": 0.0,
                "trend_score": 0.0,
                "is_limit_up": False,
                "is_limit_down": False,
                "is_st": False,
                "is_suspended": True,  # 无数据=可能停牌
            })
            continue

        # 过滤 ST 股
        is_st = "ST" in raw.get("name", "") or "*ST" in raw.get("name", "")

        # 判断停牌 (价格为0或成交量为0且非新股)
        is_suspended = raw["price"] == 0 and raw["volume_ratio"] == 0

        # 涨停/跌停判断 (考虑科创板20%、主板10%、ST 5%)
        if is_st:
            limit_up_threshold = 4.9
            limit_down_threshold = -4.9
        elif code.startswith(("688", "300", "301")) or code.startswith("8"):
            limit_up_threshold = 19.5
            limit_down_threshold = -19.5
        else:
            limit_up_threshold = 9.5
            limit_down_threshold = -9.5

        is_limit_up = raw["change_pct"] >= limit_up_threshold and raw["price"] > 0
        is_limit_down = raw["change_pct"] <= limit_down_threshold and raw["price"] > 0

        # 趋势评分
        trend_score = _compute_trend_score(
            change_pct=raw["change_pct"],
            volume_ratio=raw["volume_ratio"],
            turnover_pct=raw["turnover_pct"],
        )

        results.append({
            "code": code,
            "sector": config.STOCK_SECTOR_MAP.get(code, ""),
            "name": raw["name"],
            "return": raw["change_pct"],
            "price": raw["price"],
            "volume_ratio": round(raw["volume_ratio"], 2),
            "turnover_pct": raw["turnover_pct"],
            "pe_ttm": raw["pe_ttm"],
            "pb": raw["pb"],
            "mcap_yi": raw["mcap_yi"],
            "trend_score": round(trend_score, 2),
            "is_limit_up": is_limit_up,
            "is_limit_down": is_limit_down,
            "is_st": is_st,
            "is_suspended": is_suspended,
        })

        # 更新名称缓存
        config.STOCK_NAMES[code] = raw["name"]

    # 统计
    active = sum(1 for s in results if not s["is_suspended"])
    limit_up = sum(1 for s in results if s["is_limit_up"])
    limit_down = sum(1 for s in results if s["is_limit_down"])

    logger.info(
        f"个股行情: 活跃{active}只, 涨停{limit_up}, 跌停{limit_down}, "
        f"停牌/缺失{len(results)-active}只"
    )

    return results


def _compute_trend_score(
    change_pct: float,
    volume_ratio: float,
    turnover_pct: float,
) -> float:
    """
    计算个股趋势评分 (0-10)

    权重:
      - 涨跌幅 40%: 映射 [-10%, +10%] → [0, 10]
      - 量比 35%: 映射 [0, 5x] → [0, 10] (放量是积极信号但要防出货)
      - 换手率 25%: 映射 [0, 15%] → [0, 10] (活跃度)

    量比>3 不是加分项，适中量比(1.2-2.5)最佳
    """
    from config import STOCK_RETURN_WEIGHT, STOCK_VOLUME_WEIGHT, STOCK_TURNOVER_WEIGHT

    # 涨跌幅得分
    return_score = max(0, min(10, (change_pct + 10) / 2))

    # 量比得分 — 最佳区间 [1.0, 2.5], 过高或过低扣分
    if volume_ratio <= 0:
        vol_score = 5.0
    elif volume_ratio < 0.5:
        vol_score = volume_ratio / 0.5 * 4  # 极度缩量 0-4分
    elif volume_ratio <= 1.0:
        vol_score = 4 + (volume_ratio - 0.5) / 0.5 * 2  # 0.5-1.0: 4-6分
    elif volume_ratio <= 2.5:
        vol_score = 6 + (volume_ratio - 1.0) / 1.5 * 4  # 1.0-2.5: 6-10分 (最佳)
    elif volume_ratio <= 5.0:
        vol_score = 10 - (volume_ratio - 2.5) / 2.5 * 4  # 2.5-5.0: 10-6分
    else:
        vol_score = max(0, 6 - (volume_ratio - 5.0) / 5 * 6)  # >5x: 递减

    # 换手率得分 — 最佳区间 [2%, 10%]
    if turnover_pct <= 0:
        turnover_score = 3.0
    elif turnover_pct < 1.0:
        turnover_score = 3 + turnover_pct / 1.0 * 2  # 0-1%: 3-5分
    elif turnover_pct <= 10.0:
        turnover_score = 5 + (turnover_pct - 1.0) / 9.0 * 5  # 1-10%: 5-10分
    elif turnover_pct <= 20.0:
        turnover_score = 10 - (turnover_pct - 10.0) / 10.0 * 4  # 10-20%: 10-6分
    else:
        turnover_score = max(0, 6 - (turnover_pct - 20.0) / 10.0 * 6)

    score = (
        STOCK_RETURN_WEIGHT * return_score
        + STOCK_VOLUME_WEIGHT * vol_score
        + STOCK_TURNOVER_WEIGHT * turnover_score
    )

    return max(0, min(10, score))


def detect_anomalies_from_stocks(
    stocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    从个股数据中检测异常事件

    检测项:
      1. 极端放量 (量比 > 5x)
      2. 极端涨跌幅
      3. 涨停/跌停

    Returns:
        [{type, code, name, description, severity}, ...]
    """
    anomalies = []

    for s in stocks:
        if s["is_suspended"]:
            continue

        # 极端放量
        if s["volume_ratio"] >= config.QUALITY_MAX_VOLUME_RATIO:
            anomalies.append({
                "type": "extreme_volume",
                "code": s["code"],
                "name": s["name"],
                "description": (
                    f"{s['name']}({s['code']}) 量比 {s['volume_ratio']}x, "
                    f"涨跌 {s['return']}%"
                ),
                "severity": "high" if s["volume_ratio"] >= 8 else "medium",
            })

        # 涨停
        if s["is_limit_up"]:
            anomalies.append({
                "type": "limit_up",
                "code": s["code"],
                "name": s["name"],
                "description": f"{s['name']}({s['code']}) 涨停, 涨跌幅 {s['return']}%",
                "severity": "info",
            })

        # 跌停
        if s["is_limit_down"]:
            anomalies.append({
                "type": "limit_down",
                "code": s["code"],
                "name": s["name"],
                "description": f"{s['name']}({s['code']}) 跌停, 涨跌幅 {s['return']}%",
                "severity": "warning",
            })

    return anomalies
