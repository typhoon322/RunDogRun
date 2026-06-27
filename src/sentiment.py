"""
sentiment.py — 市场情绪指标采集 (同花顺热点 + 自计算)
=======================================================
数据源:
  1. 同花顺热点接口: 当日强势股 + 题材归因
  2. 自计算: 基于个股数据的涨停/跌停统计、风险评级
"""

import logging
from collections import Counter
from typing import Any

import requests

from src.utils import retry_request, safe_int

logger = logging.getLogger("quant-collector.sentiment")


def fetch_hot_stocks(date_str: str | None = None) -> list[dict[str, Any]]:
    """
    获取同花顺当日强势股 (带题材归因 reason tags)

    接口: zx.10jqka.com.cn/event/api/getharden
    特点: 零鉴权, ~125只强势股, 73ms 响应

    Returns:
        [{code, name, change_pct, reason, turnover_pct, dde_net}, ...]
    """
    from datetime import date as _date

    if date_str is None:
        from config import today_cn
        date_str = today_cn()

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date_str}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/117.0.0.0 Safari/537.36"
        )
    }

    def _request():
        return requests.get(url, headers=headers, timeout=15)

    resp = retry_request(_request, label="sentiment/ths-hot")
    if resp is None:
        logger.error("同花顺热点接口请求完全失败")
        return []

    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"同花顺热点JSON解析失败: {e}")
        return []

    if data.get("errocode", 0) != 0:
        logger.error(f"同花顺热点接口错误: {data.get('errormsg', '')}")
        return []

    rows = data.get("data") or []
    results = []
    for row in rows:
        results.append({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "change_pct": safe_int(row.get("zhangfu")),  # 注意: 同花顺返回int
            "reason": row.get("reason", ""),
            "turnover_pct": safe_int(row.get("huanshou")),
            "dde_net": safe_int(row.get("ddejingliang")),
        })

    logger.info(f"同花顺热点: 获取 {len(results)} 只强势股")
    return results


def compute_sentiment_indicators(
    stocks: list[dict[str, Any]],
    sectors: list[dict[str, Any]] | None = None,
    hot_stocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    综合计算市场情绪指标

    基于:
      1. 个股涨跌停统计 (自算)
      2. 同花顺热点题材集中度 (如果可用)
      3. 板块涨跌集中度

    Returns:
        {limit_up_count, limit_down_count, up_down_ratio,
         risk_level, top_themes, anomalies, advance_decline_ratio}
    """
    # 涨跌停统计
    limit_up_count = sum(1 for s in stocks if s.get("is_limit_up"))
    limit_down_count = sum(1 for s in stocks if s.get("is_limit_down"))

    # 涨跌比
    up_count = sum(1 for s in stocks if not s.get("is_suspended") and s.get("return", 0) > 0)
    down_count = sum(1 for s in stocks if not s.get("is_suspended") and s.get("return", 0) < 0)
    flat_count = sum(1 for s in stocks if not s.get("is_suspended") and s.get("return", 0) == 0)

    # 涨跌停比
    up_down_ratio = (
        round(limit_up_count / limit_down_count, 2) if limit_down_count > 0
        else (999.0 if limit_up_count > 0 else 1.0)
    )

    # 涨跌家数比
    advance_decline = (
        round(up_count / down_count, 2) if down_count > 0
        else (999.0 if up_count > 0 else 1.0)
    )

    # 风险等级
    risk_level = _compute_risk_level(
        limit_up_count, limit_down_count, up_down_ratio
    )

    # 热门题材 (从同花顺热点提取)
    top_themes = []
    if hot_stocks:
        all_tags = []
        for hs in hot_stocks:
            reason = hs.get("reason", "")
            if reason:
                tags = [t.strip() for t in str(reason).split("+") if t.strip()]
                all_tags.extend(tags)
        counter = Counter(all_tags)
        top_themes = [
            {"name": tag, "count": cnt}
            for tag, cnt in counter.most_common(10)
        ]

    # 异常事件汇总
    anomalies = _collect_anomalies(stocks, sectors, limit_up_count, limit_down_count)

    # 板块集中度: 涨幅最大的板块贡献了多少涨停
    sector_concentration = _sector_concentration(limit_up_count, sectors)

    result = {
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "up_down_ratio": up_down_ratio,
        "advance_decline_ratio": advance_decline,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "risk_level": risk_level,
        "top_themes": top_themes,
        "sector_concentration": sector_concentration,
        "anomalies": anomalies,
    }

    logger.info(
        f"情绪指标: 涨停{limit_up_count}, 跌停{limit_down_count}, "
        f"涨跌比{up_down_ratio}, 风险{risk_level}"
    )
    return result


def _compute_risk_level(
    limit_up: int,
    limit_down: int,
    up_down_ratio: float,
) -> str:
    """计算综合风险等级"""
    from config import RISK_HIGH_UP_DOWN_RATIO, RISK_MEDIUM_UP_DOWN_RATIO

    # 百股跌停 → 极高风险
    if limit_down >= 100:
        return "extreme"

    # 跌停多于涨停
    if limit_down > limit_up:
        return "high"

    if up_down_ratio <= RISK_HIGH_UP_DOWN_RATIO:
        return "high"
    elif up_down_ratio <= RISK_MEDIUM_UP_DOWN_RATIO:
        return "medium"
    else:
        # 百股涨停+无跌停 → 极强情绪
        if limit_up >= 80 and limit_down == 0:
            return "euphoric"
        return "low"


def _collect_anomalies(
    stocks: list[dict[str, Any]],
    sectors: list[dict[str, Any]] | None,
    limit_up_count: int,
    limit_down_count: int,
) -> list[dict[str, Any]]:
    """收集市场级异常事件"""
    anomalies = []

    # 极端涨跌停数量
    if limit_up_count >= 100:
        anomalies.append({
            "type": "extreme_limit_up",
            "description": f"涨停家数 {limit_up_count} 达到极端水平",
            "severity": "info",
        })
    if limit_down_count >= 50:
        anomalies.append({
            "type": "extreme_limit_down",
            "description": f"跌停家数 {limit_down_count} 达到警戒水平",
            "severity": "warning",
        })
    if limit_down_count >= 200:
        anomalies.append({
            "type": "panic_selling",
            "description": f"跌停家数 {limit_down_count}, 市场恐慌",
            "severity": "critical",
        })

    # 板块极端涨跌
    if sectors:
        top_sector = sectors[0] if sectors else None
        bottom_sector = sectors[-1] if sectors else None

        if top_sector and top_sector["change_pct"] >= 5.0:
            anomalies.append({
                "type": "sector_surge",
                "description": (
                    f"板块 {top_sector['name']} 大涨 {top_sector['change_pct']}%, "
                    f"领涨股 {top_sector['leader_name']}"
                ),
                "severity": "info",
            })

        if bottom_sector and bottom_sector["change_pct"] <= -5.0:
            anomalies.append({
                "type": "sector_plunge",
                "description": (
                    f"板块 {bottom_sector['name']} 大跌 {bottom_sector['change_pct']}%"
                ),
                "severity": "warning",
            })

    return anomalies


def _sector_concentration(
    limit_up_count: int,
    sectors: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """计算涨停的板块集中度"""
    if not sectors or limit_up_count == 0:
        return None

    # 取涨幅前5的板块，看它们贡献了多少涨停(近似: 用板块上涨家数比例)
    top5 = sectors[:5]
    top5_up = sum(s["up_count"] for s in top5)
    total_up = sum(s["up_count"] for s in sectors)

    concentration = round(top5_up / total_up, 2) if total_up > 0 else 0
    top_sector_names = [s["name"] for s in top5[:3]]

    return {
        "top5_up_ratio": concentration,
        "top_sectors": top_sector_names,
        "is_concentrated": concentration >= 0.5,
    }
