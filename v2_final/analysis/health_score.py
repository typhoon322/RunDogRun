"""
v2_final/analysis/health_score.py — v2.5 策略健康评分
===========================================================
综合: win_rate / volatility / sharpe / drawdown → 0-100
"""
from typing import Any


def compute_health_score(stats: dict[str, Any]) -> dict[str, Any]:
    """
    策略健康综合评分 (0-100)。

    评分维度:
      - 胜率 (0-40): win>55%=40, >50%=25, else=10
      - 波动 (0-30): vol<2%=30, <4%=20, else=10
      - 夏普 (0-20): sharpe>1=20, >0=15, else=5
      - 回撤 (0-10): dd<10%=10, <20%=5, else=0
    """
    score = 0
    details = []

    wr = stats.get("win_rate", 0)
    vol = stats.get("volatility", 0.02)
    sharpe = stats.get("sharpe", 0)
    dd = abs(stats.get("max_drawdown", 20))

    # 胜率 (40分)
    if wr > 0.55:
        score += 40
        details.append(f"胜率{wr:.0%}+40")
    elif wr > 0.50:
        score += 25
        details.append(f"胜率{wr:.0%}+25")
    else:
        score += 10
        details.append(f"胜率{wr:.0%}+10")

    # 波动惩罚 (30分)
    if vol < 0.02:
        score += 30
        details.append(f"波动{vol:.1%}+30")
    elif vol < 0.04:
        score += 20
        details.append(f"波动{vol:.1%}+20")
    else:
        score += 10
        details.append(f"波动{vol:.1%}+10")

    # 夏普 (20分)
    if sharpe > 1.0:
        score += 20
        details.append(f"sharpe{sharpe}+20")
    elif sharpe > 0:
        score += 15
        details.append(f"sharpe{sharpe}+15")
    else:
        score += 5
        details.append(f"sharpe{sharpe}+5")

    # 回撤 (10分)
    if dd < 10:
        score += 10
        details.append(f"dd{dd:.0f}%+10")
    elif dd < 20:
        score += 5
        details.append(f"dd{dd:.0f}%+5")
    else:
        details.append(f"dd{dd:.0f}%+0")

    score = min(100, score)

    # 评级
    if score >= 70:
        rating = "HEALTHY ✅"
    elif score >= 50:
        rating = "STABLE ⚡"
    elif score >= 30:
        rating = "WEAK ⚠️"
    else:
        rating = "CRITICAL 🔴"

    return {
        "health_score": score,
        "rating": rating,
        "details": details,
        "advice": _advice(rating, dd, wr),
    }


def _advice(rating: str, max_dd: float, win_rate: float) -> str:
    if rating.startswith("HEALTHY"):
        return "策略健康, 可继续运行"
    if rating.startswith("STABLE"):
        return "策略稳定, 注意风险控制"
    if rating.startswith("WEAK"):
        if max_dd > 15:
            return "建议暂停交易, 观察回撤修复"
        return "建议降低仓位, 等待信号改善"
    return "策略退化严重, 建议停止交易并复盘"
