"""
base.py — 数据提供者抽象基类
=============================
所有数据源必须实现此接口, 支持可插拔切换
"""
from typing import Any


class DataProvider:
    """统一数据接口"""

    def get_index(self) -> list[dict[str, Any]]:
        """获取主要指数行情"""
        raise NotImplementedError

    def get_stocks(self, codes: list[str] | None = None) -> list[dict[str, Any]]:
        """获取个股行情"""
        raise NotImplementedError

    def get_sectors(self) -> list[dict[str, Any]]:
        """获取行业板块排行"""
        raise NotImplementedError

    def get_sentiment(self) -> dict[str, Any]:
        """获取市场情绪指标 (涨停/跌停数等)"""
        raise NotImplementedError

    def health_check(self) -> bool:
        """检查数据源是否可用"""
        return True

    @property
    def name(self) -> str:
        return self.__class__.__name__
