"""
v2_final/strategy/market_state.py — v2.4 市场状态 (极简)
===========================================================
只有两种状态: OK_TRADE (MA5>MA20) / NO_TRADE
"""
import logging
from typing import Any

logger = logging.getLogger("v2.market_state")


def get_market_state(symbol: str = "000001") -> str:
    """
    基于上证指数 MA5 vs MA20 判断市场状态。

    Returns:
        "OK_TRADE" 或 "NO_TRADE"
    """
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol="sh000001")
        if len(df) < 20:
            return "NO_TRADE"

        ma5 = df["close"].rolling(5).mean().iloc[-1]
        ma20 = df["close"].rolling(20).mean().iloc[-1]

        state = "OK_TRADE" if ma5 > ma20 else "NO_TRADE"
        logger.info(f"市场状态: {state} (MA5={ma5:.1f} MA20={ma20:.1f})")
        return state

    except Exception as e:
        logger.warning(f"市场状态获取失败: {e}")
        return "NO_TRADE"  # 默认保守
