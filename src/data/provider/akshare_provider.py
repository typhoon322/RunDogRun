"""
akshare_provider.py — AKShare 免费数据源
==========================================
覆盖指数/个股/板块, 免费免key
"""
import logging
from typing import Any

from src.data.provider.base import DataProvider

logger = logging.getLogger("quant.data.akshare")


class AKShareProvider(DataProvider):

    def __init__(self):
        self._available = None

    @property
    def name(self) -> str:
        return "akshare"

    def health_check(self) -> bool:
        if self._available is None:
            try:
                import akshare as ak
                df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260101")
                self._available = len(df) > 0
            except Exception as e:
                logger.warning(f"AkShare 不可用: {e}")
                self._available = False
        return self._available

    def get_index(self) -> list[dict[str, Any]]:
        if not self.health_check():
            return []
        try:
            import akshare as ak
            indices = []
            codes = {"000001": "上证指数", "399001": "深证成指", "000300": "沪深300"}
            for code, name in codes.items():
                try:
                    df = ak.index_zh_a_hist(symbol=code, period="daily", start_date="20260101")
                    if not df.empty:
                        row = df.tail(1).iloc[0]
                        indices.append({
                            "code": code, "name": name,
                            "price": float(row.get("收盘", 0)),
                            "open": float(row.get("开盘", 0)),
                            "high": float(row.get("最高", 0)),
                            "low": float(row.get("最低", 0)),
                            "change_pct": float(row.get("涨跌幅", 0)),
                            "amount_wan": float(row.get("成交额", 0)) / 10000,
                            "volume_ratio": 1.0,
                        })
                except Exception:
                    pass
            return indices
        except Exception as e:
            logger.error(f"AkShare 指数获取失败: {e}")
            return []

    def get_stocks(self, codes: list[str] | None = None) -> list[dict[str, Any]]:
        if not self.health_check():
            return []
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df.empty:
                return []
            stocks = []
            for _, row in df.iterrows():
                code = str(row.get("代码", ""))
                if codes and code not in codes:
                    continue
                stocks.append({
                    "code": code,
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "volume_ratio": float(row.get("量比", 1.0)),
                    "turnover_pct": float(row.get("换手率", 0)),
                    "pe_ttm": float(row.get("市盈率-动态", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "open": float(row.get("今开", 0)),
                    "last_close": float(row.get("昨收", 0)),
                    "mcap_yi": float(row.get("总市值", 0)) / 1e8,
                })
            return stocks
        except Exception as e:
            logger.error(f"AkShare 个股获取失败: {e}")
            return []

    def get_sectors(self) -> list[dict[str, Any]]:
        if not self.health_check():
            return []
        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            if df.empty:
                return []
            sectors = []
            for _, row in df.iterrows():
                sectors.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "up_count": int(row.get("上涨家数", 0)),
                    "down_count": int(row.get("下跌家数", 0)),
                    "total_stocks": int(row.get("上涨家数", 0)) + int(row.get("下跌家数", 0)),
                    "leader_name": str(row.get("领涨股票", "")),
                    "leader_change_pct": float(row.get("领涨股票-涨跌幅", 0)),
                    "strength_score": 0.0,
                    "money_flow": "neutral",
                })
            return sectors
        except Exception as e:
            logger.error(f"AkShare 板块获取失败: {e}")
            return []

    def get_sentiment(self) -> dict[str, Any]:
        if not self.health_check():
            return {"limit_up_count": 0, "limit_down_count": 0, "risk_level": "unknown"}
        try:
            import akshare as ak
            # 涨跌停统计
            df = ak.stock_zt_pool_em(date="20260101")
            limit_up = len(df) if not df.empty else 0
            df2 = ak.stock_zt_pool_dtgc_em(date="20260101")
            limit_down = len(df2) if not df2.empty else 0
            return {
                "limit_up_count": limit_up,
                "limit_down_count": limit_down,
                "risk_level": "low" if limit_up > limit_down * 3 else "medium",
            }
        except Exception:
            return {"limit_up_count": 0, "limit_down_count": 0, "risk_level": "unknown"}
