"""
v2_final/analysis/monitor.py — v2.5 统一监控核心
====================================================
收敛所有监控逻辑到一个模块: 指标计算 + 健康评分 + 状态机

系统只回答3个问题:
  1. 还能不能用? (health score)
  2. 风险有没有变大? (drawdown)
  3. 现在该不该用? (status)
"""
from collections import deque
from typing import Any


# ── 1. 统一指标计算 ──

def calc_metrics(equity_curve: list[float]) -> dict[str, Any] | None:
    """统一收益/风险指标计算 (修复精度)"""
    n = len(equity_curve)
    if n < 2:
        return None

    # 日收益率序列
    returns = [
        (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
        for i in range(1, n)
    ]

    win_rate = sum(1 for r in returns if r > 0) / len(returns)

    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / len(returns)
    volatility = var ** 0.5

    # 最大回撤
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)

    total_return = round((equity_curve[-1] / equity_curve[0] - 1) * 100, 2)

    return {
        "total_return_pct": total_return,
        "win_rate": round(win_rate, 3),
        "volatility": round(volatility, 4),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "n_days": n,
    }


# ── 2. 健康评分 (0-100) ──

def health_score(metrics: dict[str, Any]) -> dict[str, Any]:
    """
    三维护康评分:
      - 胜率 (40分): >55%=40, >50%=25, else=10
      - 回撤 (30分): <5%=30, <8%=20, else=5
      - 波动 (30分): <2%=30, <4%=20, else=10
    """
    wr = metrics.get("win_rate", 0)
    dd = abs(metrics.get("max_drawdown_pct", 20))
    vol = metrics.get("volatility", 0.02)

    # 胜率
    if wr >= 0.55:
        wr_score = 40
    elif wr >= 0.50:
        wr_score = 25
    else:
        wr_score = 10

    # 回撤
    if dd < 5:
        dd_score = 30
    elif dd < 8:
        dd_score = 20
    else:
        dd_score = 5

    # 波动
    if vol < 0.02:
        vol_score = 30
    elif vol < 0.04:
        vol_score = 20
    else:
        vol_score = 10

    score = min(100, wr_score + dd_score + vol_score)

    if score >= 70:
        rating = "HEALTHY ✅"
    elif score >= 50:
        rating = "STABLE ⚡"
    else:
        rating = "WEAK ⚠️"

    return {
        "health_score": score,
        "rating": rating,
        "breakdown": {
            "win_rate_score": wr_score,
            "drawdown_score": dd_score,
            "volatility_score": vol_score,
        },
    }


# ── 3. 系统状态机 ──

def get_status(score: int, max_dd_pct: float) -> str:
    """
    三态判定:
      TRADE:  评分>=70 且 回撤<6%  → 可正常交易
      CAUTION: 评分>=50              → 谨慎, 降仓
      STOP:    评分<50               → 停止
    """
    if score >= 70 and abs(max_dd_pct) < 6:
        return "TRADE"
    if score >= 50:
        return "CAUTION"
    return "STOP"


# ── 4. 滚动监控 ──

class RollingMonitor:
    """20日滚动窗口 — 净值 + 评分趋势"""

    def __init__(self, window: int = 20):
        self.window = window
        self.equity = deque(maxlen=window)
        self.scores = deque(maxlen=window)

    def update(self, value: float, score: int) -> None:
        self.equity.append(round(value, 4))
        self.scores.append(score)

    def trend(self) -> str:
        """评分趋势: improving / stable / declining"""
        if len(self.scores) < 5:
            return "insufficient_data"
        recent = list(self.scores)[-5:]
        if recent[-1] > recent[0] + 3:
            return "improving ↗"
        elif recent[-1] < recent[0] - 3:
            return "declining ↘"
        return "stable →"

    def current_drawdown(self) -> float:
        eq = list(self.equity)
        if not eq:
            return 0.0
        peak = max(eq)
        return round((peak - eq[-1]) / peak * 100, 2) if peak > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        eq = list(self.equity)
        return {
            "n": len(eq),
            "latest_value": eq[-1] if eq else 1.0,
            "trend": self.trend(),
            "current_drawdown_pct": self.current_drawdown(),
            "score_trend": list(self.scores)[-5:] if self.scores else [],
        }


# ── 5. 一键分析 ──

def analyze(equity_curve: list[float]) -> dict[str, Any]:
    """统一分析入口 — 指标→健康→状态→建议"""
    metrics = calc_metrics(equity_curve)
    if metrics is None:
        return {"status": "STOP", "health_score": 0, "rating": "NO DATA",
                "breakdown": {}, "note": "insufficient data"}

    health = health_score(metrics)
    status = get_status(health["health_score"], metrics["max_drawdown_pct"])

    note = {
        "TRADE": "策略健康, 可正常交易",
        "CAUTION": "建议降仓, 观察回撤",
        "STOP": "策略退化, 暂停交易",
    }.get(status, "")

    return {
        "status": status,
        "health_score": health["health_score"],
        "rating": health["rating"],
        "breakdown": health["breakdown"],
        "metrics": metrics,
        "note": note,
    }
