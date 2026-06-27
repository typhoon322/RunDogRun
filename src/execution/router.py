"""
router.py — 统一执行路由器
=============================
v9 仿真 / v10 实盘 双模式切换
"""
import logging
from typing import Any

from src.v9_sim.execution_engine import SimulationEngine
from src.v10_live.broker_adapter import create_broker, BrokerAPI
from src.v10_live.risk_gate import RiskGatekeeper

logger = logging.getLogger("quant.execution.router")


class ExecutionRouter:
    """执行路由器 — v9仿真 / v10实盘 统一入口"""

    def __init__(self, mode: str = "sim"):
        self.mode = mode
        self.sim_engine = SimulationEngine(slippage_bps=3.0)
        self.broker: BrokerAPI = create_broker("mock" if mode == "sim" else "live")
        self.gatekeeper = RiskGatekeeper()
        self.execution_log: list[dict] = []

    def execute(self, signal: dict, market_price: float,
                portfolio: dict | None = None) -> dict[str, Any]:
        """
        执行交易信号。

        Args:
            signal: v8 输出的交易信号 {action, code, price, position_size}
            market_price: 当前市价
            portfolio: 当前组合状态 (用于风控)

        Returns:
            执行结果
        """
        order = {
            "side": self._action_to_side(signal.get("action", "HOLD")),
            "price": signal.get("price", market_price),
            "size": signal.get("position_size", 0),
            "symbol": signal.get("code", ""),
        }

        # 实盘模式前置检查
        if self.mode == "live":
            pf = portfolio or {"total_exposure": 0, "drawdown_pct": 0}
            allowed, reason = self.gatekeeper.pre_trade_check(order, pf)
            if not allowed:
                return {"mode": "live", "filled": False, "rejected": True, "reason": reason}

        # HOLD 信号不执行
        if order["side"] == "HOLD" or order["size"] <= 0:
            return {"mode": self.mode, "filled": False, "reason": "HOLD or zero-size"}

        # 执行
        if self.mode == "sim":
            result = self.sim_engine.execute(order, market_price)
        else:
            result = self.broker.send_order(order)
            result["mode"] = "live"

        self.execution_log.append(result)
        return result

    @staticmethod
    def _action_to_side(action: str) -> str:
        action_map = {
            "BUY": "BUY", "BUY_TRIAL": "BUY", "ADD": "BUY",
            "SELL": "SELL", "REDUCE": "SELL", "EMPTY": "SELL",
            "HOLD": "HOLD", "HOLD_CORE": "HOLD", "NO_ACTION": "HOLD",
        }
        return action_map.get(action, "HOLD")

    def get_metrics(self) -> dict[str, Any]:
        if self.mode == "sim":
            return self.sim_engine.get_metrics()
        return {
            "mode": "live",
            "total_orders": len(self.execution_log),
            "risk_status": self.gatekeeper.get_status(),
        }
