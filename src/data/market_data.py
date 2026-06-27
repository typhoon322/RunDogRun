"""
market.py — 大盘指数数据采集 (腾讯财经 HTTP)
============================================
数据源: 腾讯财经 qt.gtimg.cn
特点: 不封IP, GBK编码, ~分隔88字段, 一次批量拉取
"""

import logging
from typing import Any

import requests

import config
from src.utils import safe_float, retry_request

logger = logging.getLogger("quant-collector.market")


def _build_tencent_codes(index_codes: list[str]) -> list[str]:
    """构造腾讯财经代码前缀: 6开头→sh, 0/3开头→sz, 8开头→bj"""
    prefixed = []
    for c in index_codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    return prefixed


def fetch_index_quotes(index_codes: list[str] | None = None) -> list[dict[str, Any]]:
    """
    获取指数行情数据。

    腾讯财经字段 (索引):
      1=名称, 3=当前价, 4=昨收, 5=今开, 31=涨跌额, 32=涨跌幅%,
      33=最高, 34=最低, 37=成交额(万), 38=换手率%, 39=PE(TTM),
      44=总市值(亿), 45=流通市值(亿), 46=PB, 49=量比

    Returns:
        [{code, name, price, last_close, open, high, low,
          change_pct, change_amt, amount_wan, volume_ratio,
          pe_ttm, pb, mcap_yi, float_mcap_yi}, ...]
    """
    if index_codes is None:
        index_codes = config.INDEX_LIST

    prefixed = _build_tencent_codes(index_codes)
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)

    def _request():
        headers = {"User-Agent": "Mozilla/5.0"}
        return requests.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)

    try:
        resp = retry_request(
            lambda: _request(),
            label="market/tencent",
        )
        if resp is None:
            logger.error("腾讯财经指数行情请求完全失败")
            return []

        resp.encoding = "gbk"
        data = resp.text
    except Exception as e:
        logger.error(f"腾讯财经指数行情解码失败: {e}")
        return []

    results = []
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue

        try:
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 53:
                continue

            code = key[2:]  # 去掉 sh/sz/bj 前缀
            result = {
                "code": code,
                "name": vals[1] or config.INDEX_NAMES.get(code, f"指数{code}"),
                "price": safe_float(vals[3]),
                "last_close": safe_float(vals[4]),
                "open": safe_float(vals[5]),
                "high": safe_float(vals[33]),
                "low": safe_float(vals[34]),
                "change_pct": round(safe_float(vals[32]), 2),
                "change_amt": safe_float(vals[31]),
                "amount_wan": safe_float(vals[37]),
                "volume_ratio": safe_float(vals[49]),
                "pe_ttm": safe_float(vals[39]),
                "pb": safe_float(vals[46]),
                "mcap_yi": safe_float(vals[44]),
                "float_mcap_yi": safe_float(vals[45]),
            }
            results.append(result)
        except (IndexError, ValueError) as e:
            logger.warning(f"解析指数数据行失败: {e}, line={line[:80]}...")
            continue

    # 按原始顺序排序
    code_order = {c: i for i, c in enumerate(index_codes)}
    results.sort(key=lambda x: code_order.get(x["code"], 999))

    logger.info(f"指数行情: 获取 {len(results)}/{len(index_codes)} 个指数")
    return results


def compute_market_summary(indices: list[dict[str, Any]]) -> dict[str, Any]:
    """
    基于指数数据计算大盘汇总指标

    Returns:
        {overall_return, overall_volume_ratio, advance_decline_ratio, market_status}
    """
    if not indices:
        return {
            "overall_return": 0.0,
            "overall_volume_ratio": 1.0,
            "market_status": "unknown",
        }

    # 主要指数涨跌幅
    main_indices = {"000001", "399001", "000300"}
    main_returns = [
        idx["change_pct"]
        for idx in indices
        if idx["code"] in main_indices
    ]

    overall_return = (
        sum(main_returns) / len(main_returns) if main_returns else 0.0
    )

    # 量比（取主要指数均值）
    volume_ratios = [
        idx["volume_ratio"]
        for idx in indices
        if idx["volume_ratio"] > 0
    ]
    overall_volume_ratio = (
        sum(volume_ratios) / len(volume_ratios) if volume_ratios else 1.0
    )

    # 市场状态
    if overall_return > 1.5:
        market_status = "strong_bull"
    elif overall_return > 0.3:
        market_status = "mild_bull"
    elif overall_return > -0.3:
        market_status = "neutral"
    elif overall_return > -1.5:
        market_status = "mild_bear"
    else:
        market_status = "strong_bear"

    return {
        "overall_return": round(overall_return, 2),
        "overall_volume_ratio": round(overall_volume_ratio, 2),
        "market_status": market_status,
    }
