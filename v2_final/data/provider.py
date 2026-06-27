"""
v2_final/data/provider.py — 统一数据接口
==========================================
AkShare 免费数据 → 统一归一化输出
"""
import logging
from typing import Any

logger = logging.getLogger("v2.data")


def get_market_data() -> dict[str, list[dict]]:
    """获取全市场数据 (指数/板块/个股)"""
    result = {"indices": [], "sectors": [], "stocks": []}

    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 未安装, 返回空数据")
        return result

    # 指数
    try:
        df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260101")
        if not df.empty:
            row = df.tail(1).iloc[0]
            result["indices"] = [{
                "code": "000001", "name": "上证指数",
                "price": float(row["收盘"]), "change_pct": float(row["涨跌幅"]),
            }]
    except Exception:
        pass

    # 板块
    try:
        df = ak.stock_board_industry_name_em()
        result["sectors"] = [
            {"name": str(r["板块名称"]), "change_pct": float(r["涨跌幅"]),
             "up_count": int(r.get("上涨家数", 0)), "down_count": int(r.get("下跌家数", 0)),
             "leader": str(r.get("领涨股票", ""))}
            for _, r in df.iterrows()
        ]
    except Exception:
        pass

    # 个股
    try:
        df = ak.stock_zh_a_spot_em()
        result["stocks"] = [
            {"code": str(r["代码"]), "name": str(r["名称"]),
             "price": float(r["最新价"]), "change_pct": float(r["涨跌幅"]),
             "volume": float(r["成交量"]), "amount": float(r["成交额"]),
             "turnover": float(r.get("换手率", 0)), "pe": float(r.get("市盈率-动态", 0)),
             "mcap": float(r.get("总市值", 0)) / 1e8}
            for _, r in df.iterrows()
        ]
    except Exception:
        pass

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
