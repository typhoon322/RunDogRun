"""
broker_adapter.py — v10 实盘券商接口
========================================
统一 BrokerAPI → Mock/Live 可切换
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("quant.v10.broker")


class BrokerAPI(ABC):
    """券商接口抽象基类"""

    @abstractmethod
    def send_order(self, order: dict) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_position(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        raise NotImplementedError


class MockBroker(BrokerAPI):
    """模拟券商 — 测试用"""

    def __init__(self):
        self._orders: list[dict] = []
        self._position = {"cash": 1000000.0, "holdings": {}, "total_value": 1000000.0}
        self._order_id = 0

    def send_order(self, order: dict) -> dict[str, Any]:
        self._order_id += 1
        oid = f"MOCK-{self._order_id:06d}"
        result = {
            "order_id": oid,
            "status": "accepted",
            "symbol": order.get("symbol", ""),
            "side": order.get("side", "BUY"),
            "quantity": order.get("size", 0),
            "price": order.get("price", 0),
            "filled_price": order.get("price", 0),
            "message": "mock fill",
        }
        self._orders.append(result)
        logger.info(f"Mock order: {oid} {order.get('side')} @ {order.get('price')}")
        return result

    def get_position(self) -> dict[str, Any]:
        return self._position

    def get_account(self) -> dict[str, Any]:
        return {
            "broker": "mock",
            "account_id": "MOCK-001",
            "total_value": self._position["total_value"],
            "cash": self._position["cash"],
        }


class LiveBroker(BrokerAPI):
    """实盘券商 — 替换为真实 API"""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self._connected = False

    def connect(self) -> bool:
        """连接券商 (替换为真实连接逻辑)"""
        # TODO: 替换为真实券商 SDK 连接
        self._connected = True
        logger.info("LiveBroker: connected")
        return True

    def send_order(self, order: dict) -> dict[str, Any]:
        if not self._connected:
            return {"order_id": "", "status": "error", "message": "not connected"}

        # TODO: 替换为真实券商下单 API
        raise NotImplementedError("替换为真实券商 API: 如 easytrader/xtquant/通达信")

    def get_position(self) -> dict[str, Any]:
        # TODO: 真实持仓查询
        raise NotImplementedError

    def get_account(self) -> dict[str, Any]:
        # TODO: 真实账户查询
        raise NotImplementedError


def create_broker(mode: str = "mock") -> BrokerAPI:
    """创建券商实例"""
    if mode == "live":
        return LiveBroker()
    return MockBroker()
