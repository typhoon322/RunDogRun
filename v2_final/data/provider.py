"""
v2_final/data/provider.py — 统一数据接口
==========================================
AkShare 免费数据 → 统一归一化输出
"""
import logging
import math
from typing import Any

logger = logging.getLogger("v2.data")


def _safe_float(x, default=0.0):
    try:
        v = float(x)
        return v if not math.isnan(v) else default
    except (TypeError, ValueError):
        return default


def _safe_int(x, default=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def get_market_data() -> dict[str, list[dict]]:
    """获取全市场数据 (指数/板块/个股) — 含重试机制"""
    result = {"indices": [], "sectors": [], "stocks": []}

    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 未安装, 返回空数据")
        return result

    import time

    # 指数 (最多重试3次)
    for attempt in range(3):
        try:
            df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260101")
            if not df.empty:
                row = df.tail(1).iloc[0]
                result["indices"] = [{
                    "code": "000001", "name": "上证指数",
                    "price": _safe_float(row["收盘"]), "change_pct": _safe_float(row["涨跌幅"]),
                }]
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
            else:
                logger.warning("指数数据获取失败(重试3次)")

    # 板块 (最多重试3次)
    for attempt in range(3):
        try:
            df = ak.stock_board_industry_name_em()
            result["sectors"] = [
                {"name": str(r["板块名称"]), "change_pct": _safe_float(r["涨跌幅"]),
                 "up_count": _safe_int(r.get("上涨家数", 0)), "down_count": _safe_int(r.get("下跌家数", 0)),
                 "leader": str(r.get("领涨股票", ""))}
                for _, r in df.iterrows()
            ]
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
            else:
                logger.warning("板块数据获取失败(重试3次)")

    # 个股 (最多重试3次, CI环境更宽容)
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_spot_em()
            result["stocks"] = [
                {"code": str(r["代码"]), "name": str(r["名称"]),
                 "price": _safe_float(r["最新价"]), "change_pct": _safe_float(r["涨跌幅"]),
                 "volume": _safe_float(r["成交量"]), "amount": _safe_float(r["成交额"]),
                 "turnover": _safe_float(r.get("换手率", 0)), "pe": _safe_float(r.get("市盈率-动态", 0)),
                 "mcap": _safe_float(r.get("总市值", 0)) / 1e8}
                for _, r in df.iterrows()
            ]
            break
        except Exception:
            if attempt < 2:
                time.sleep(3)
            else:
                logger.warning("个股数据获取失败(重试3次)")

    logger.info(f"数据: {len(result['indices'])}指数 {len(result['sectors'])}板块 {len(result['stocks'])}个股")
    return result


def get_daily_data(symbol: str = "000001", start_date: str = "20240101",
                   end_date: str = "20261231", adjust: str = "qfq"):
    """
    获取个股日线历史 K 线 (用于回测)

    Returns:
        pandas DataFrame with columns: date, open, high, low, close, volume, pct
    """
    import akshare as ak
    import pandas as pd

    logger.info(f"获取 {symbol} 日线数据 {start_date}→{end_date}")

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except Exception:
        # fallback: try without adjust
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                     start_date=start_date, end_date=end_date)
        except Exception:
            logger.warning(f"无法获取 {symbol} 历史数据")
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "pct"])

    if df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "pct"])

    df = df.rename(columns={
        "日期": "date", "收盘": "close", "开盘": "open",
        "最高": "high", "最低": "low", "成交量": "volume", "涨跌幅": "pct",
    })

    logger.info(f"  获取 {len(df)} 条日线数据")
    return df
