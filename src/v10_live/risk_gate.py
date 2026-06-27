"""
risk_gate.py — v10 实盘风控前置
==================================
预交易检查 / 熔断 / 冷却 / 仓位限制
"""
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("quant.v10.risk_gate")


class RiskGatekeeper:
    """实盘风控守门人"""

    def __init__(self):
        self.max_exposure = 0.70           # 最大总仓位
        self.max_single_order = 0.30       # 单笔最大
        self.max_daily_trades = 20         # 单日最大交易次数
        self.max_drawdown = 0.05           # 熔断阈值 5%
        self.cooldown_seconds = 60         # 冷却时间
        self._last_trade_time = 0.0
        self._daily_trades = 0
        self._circuit_breaker = False

    def pre_trade_check(self, order: dict, portfolio: dict) -> tuple[bool, str]:
        """预交易检查 — 返回 (是否允许, 原因)"""
        # 熔断
        if self._circuit_breaker:
            return False, "circuit_breaker: 熔断保护已触发"

        # 回撤熔断
        drawdown = portfolio.get("drawdown_pct", 0)
        if abs(drawdown) >= self.max_drawdown * 100:
            self._circuit_breaker = True
            return False, f"circuit_breaker: 回撤 {drawdown}% 超过 {self.max_drawdown*100}%"

        # 仓位检查
        exposure = portfolio.get("total_exposure", 0)
        if exposure >= self.max_exposure:
            return False, f"仓位超限: {exposure:.0%} >= {self.max_exposure:.0%}"

        # 单笔限制
        size = order.get("size", 0) or order.get("position_size", 0)
        if size > self.max_single_order:
            return False, f"单笔超限: {size:.0%} > {self.max_single_order:.0%}"

        # 日交易次数
        if self._daily_trades >= self.max_daily_trades:
            return False, f"日交易次数超限: {self._daily_trades}"

        # 冷却
        now = datetime.now().timestamp()
        if now - self._last_trade_time < self.cooldown_seconds:
            wait = self.cooldown_seconds - (now - self._last_trade_time)
            return False, f"冷却中: 还需等待 {wait:.0f}s"

        # 通过
        self._last_trade_time = now
        self._daily_trades += 1
        return True, "ok"

    def reset_circuit(self) -> None:
        """重置熔断 (手动)"""
        self._circuit_breaker = False
        self._daily_trades = 0
        logger.info("熔断已重置")

    def get_status(self) -> dict[str, Any]:
        return {
            "circuit_breaker": self._circuit_breaker,
            "daily_trades": self._daily_trades,
            "max_daily": self.max_daily_trades,
            "cooldown_seconds": self.cooldown_seconds,
        }
