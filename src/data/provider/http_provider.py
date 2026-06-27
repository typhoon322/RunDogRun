"""
http_provider.py — 腾讯+东财 HTTP 直连数据源
===============================================
零依赖, 直接 HTTP 调用, 海外可用
"""
import logging
from typing import Any

from src.data.provider.base import DataProvider

logger = logging.getLogger("quant.data.http")


class HTTPProvider(DataProvider):
    """腾讯财经 + 东财 push2 直连"""

    def __init__(self):
        self._available = None

    @property
    def name(self) -> str:
        return "http"

    def health_check(self) -> bool:
        if self._available is None:
            try:
                import requests
                resp = requests.get("https://qt.gtimg.cn/q=sh000001",
                                   headers={"User-Agent": "Mozilla/5.0"},
                                   timeout=5)
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
        return self._available

    def get_index(self) -> list[dict[str, Any]]:
        from src.data.market_data import fetch_index_quotes
        return fetch_index_quotes()

    def get_stocks(self, codes: list[str] | None = None) -> list[dict[str, Any]]:
        from src.data.stock_data import fetch_stock_quotes
        return fetch_stock_quotes(codes)

    def get_sectors(self) -> list[dict[str, Any]]:
        from src.data.sector_data import fetch_industry_sectors
        return fetch_industry_sectors()

    def get_sentiment(self) -> dict[str, Any]:
        try:
            from src.data.sentiment_data import fetch_hot_stocks
            hot = fetch_hot_stocks()
            return {
                "limit_up_count": len(hot),
                "limit_down_count": 0,
                "risk_level": "medium",
                "hot_stocks": hot[:20],
            }
        except Exception:
            return {"limit_up_count": 0, "limit_down_count": 0, "risk_level": "unknown"}
