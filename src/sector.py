"""
sector.py — 行业板块排名数据采集 (东财 push2)
=============================================
数据源: push2.eastmoney.com/api/qt/clist/get (m:90+t:2)
特点: 零鉴权, ~100个东财行业板块, 含涨跌幅/上涨下跌家数/领涨股
"""

import logging
from typing import Any

from src.utils import em_get, retry_request, safe_float, safe_int

logger = logging.getLogger("quant-collector.sector")


def fetch_industry_sectors() -> list[dict[str, Any]]:
    """
    获取全市场行业板块排名。

    东财 push2 字段:
      f2=最新价, f3=涨跌幅%, f4=涨跌额
      f12=板块代码, f14=板块名称
      f104=上涨家数, f105=下跌家数, f128=平盘家数
      f136=领涨股涨跌幅, f140=领涨股名称, f141=领涨股代码
      f207=领涨股最新价

    Returns:
        [{code, name, change_pct, change_amt, up_count, down_count,
          flat_count, leader_name, leader_code, leader_change_pct,
          strength_score, money_flow}, ...]
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "120",       # 全行业板块约100个
        "po": "1",          # 按涨跌幅降序
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fs": "m:90+t:2",  # 东财行业板块
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }

    def _request():
        return em_get(url, params=params)

    resp = retry_request(_request, label="sector/eastmoney")
    if resp is None:
        logger.error("东财行业板块数据请求完全失败")
        return []

    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"东财行业板块JSON解析失败: {e}")
        return []

    items = data.get("data", {}).get("diff", [])
    if not items:
        logger.warning("东财行业板块返回空数据")
        return []

    sectors = []
    for i, item in enumerate(items):
        name = item.get("f14", "")
        change_pct = safe_float(item.get("f3"))
        up_count = safe_int(item.get("f104"))
        down_count = safe_int(item.get("f105"))
        total = up_count + down_count + safe_int(item.get("f128"))

        # 计算板块强度评分 (0-10)
        strength_score = _compute_strength_score(
            change_pct=change_pct,
            up_count=up_count,
            down_count=down_count,
            total=total,
            rank=i + 1,
            total_sectors=len(items),
        )

        # 资金流向信号
        money_flow = _money_flow_signal(change_pct, up_count, down_count)

        sectors.append({
            "code": item.get("f12", ""),
            "name": name,
            "change_pct": round(change_pct, 2),
            "change_amt": safe_float(item.get("f4")),
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": safe_int(item.get("f128")),
            "total_stocks": total,
            "leader_name": item.get("f140", ""),
            "leader_code": item.get("f141", ""),
            "leader_change_pct": safe_float(item.get("f136")),
            "strength_score": round(strength_score, 2),
            "momentum_3d": round(change_pct, 2),  # v1: 用当日涨跌近似
            "money_flow": money_flow,
        })

    logger.info(f"行业板块: 获取 {len(sectors)} 个板块")
    return sectors


def _compute_strength_score(
    change_pct: float,
    up_count: int,
    down_count: int,
    total: int,
    rank: int,
    total_sectors: int,
) -> float:
    """
    计算板块强度评分 (0-10)。

    权重:
      - 涨跌幅 50%: 映射 [-5%, +10%] → [0, 10]
      - 上涨家数占比 30%: [0%, 100%] → [0, 10]
      - 排名因子 20%: 排名越靠前分越高
    """
    # 涨跌幅得分 (非线性映射，涨停板板块=10)
    change_score = max(0, min(10, (change_pct + 5) / 1.5))

    # 上涨家数占比得分
    if total > 0:
        up_ratio = up_count / total
        up_score = up_ratio * 10
    else:
        up_score = 5.0

    # 排名得分
    rank_score = max(0, (1 - rank / total_sectors) * 10)

    from config import SECTOR_CHANGE_WEIGHT, SECTOR_UP_RATIO_WEIGHT, SECTOR_LEADER_WEIGHT

    score = (
        SECTOR_CHANGE_WEIGHT * change_score
        + SECTOR_UP_RATIO_WEIGHT * up_score
        + SECTOR_LEADER_WEIGHT * rank_score
    )

    return max(0, min(10, score))


def _money_flow_signal(
    change_pct: float, up_count: int, down_count: int
) -> str:
    """判断板块资金流向信号"""
    if change_pct > 2.0 and up_count > down_count * 3:
        return "strong_inflow"
    elif change_pct > 0.5 and up_count > down_count:
        return "positive"
    elif change_pct < -2.0 and down_count > up_count * 3:
        return "strong_outflow"
    elif change_pct < -0.5 and down_count > up_count:
        return "negative"
    else:
        return "neutral"
