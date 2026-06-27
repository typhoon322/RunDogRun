"""
v2_final/execution/broker.py — 实盘接口 (预留)
=================================================
替换为真实券商 SDK: easytrader / xtquant / 通达信
"""
from typing import Any


class Broker:
    """实盘券商接口 — 替换对应 SDK"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def send(self, signal: dict) -> dict[str, Any]:
        """发送订单 (替换为真实API)"""
        # TODO: 接入 easytrader / xtquant
        return {
            "order_id": "SIM-001",
            "status": "submitted",
            "stock": signal.get("stock_code", ""),
            "action": signal.get("action", ""),
        }
