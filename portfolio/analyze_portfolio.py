"""
portfolio/analyze_portfolio.py — v2.6.1 持仓分析 & 偏离雷达
===============================================================
将"真实持仓"转化为可分析数据, 与策略 Universe 对比

输出:
  - 持仓行业分布
  - Universe 行业分布
  - 偏离雷达数据 (用于 Streamlit 图表)
  - 偏离评分 (Deviation Score 0-100)
"""
import json
import logging
import os
from collections import defaultdict

from portfolio.sector_mapper import lookup_sector

logger = logging.getLogger("portfolio.analyzer")

OUTPUT_DIR = "output"


def parse_holdings(holdings: list[dict]) -> list[dict]:
    """
    标准化持仓格式。

    Input:
        [{"code": "600487", "name": "亨通光电"}, ...]
        或简写 [{"code": "600487"}, ...]

    Returns:
        [{code, name, sector}, ...]
    """
    result = []
    for h in holdings:
        code = str(h.get("code", "")).zfill(6)
        name = h.get("name", code)
        sector = lookup_sector(code)
        result.append({"code": code, "name": name, "sector": sector})
    return result


def calc_sector_exposure(holdings: list[dict]) -> dict[str, float]:
    """
    计算持仓行业分布 (占比)。

    Returns:
        {"通信": 0.4, "新能源": 0.3, ...}
    """
    exposure: dict[str, int] = defaultdict(int)
    total = len(holdings)
    if total == 0:
        return {}

    for h in holdings:
        sector = h.get("sector", "未知")
        exposure[sector] += 1

    return {k: round(v / total, 3) for k, v in exposure.items()}


def calc_universe_exposure(universe: list[str]) -> dict[str, float]:
    """
    计算策略 Universe 行业分布。

    Args:
        universe: 策略股票代码列表 ["600487", "600522", ...]

    Returns:
        {"通信": 0.2, "新能源": 0.5, ...}
    """
    exposure: dict[str, int] = defaultdict(int)
    total = len(universe)
    if total == 0:
        return {}

    for code in universe:
        sector = lookup_sector(code)
        exposure[sector] += 1

    return {k: round(v / total, 3) for k, v in exposure.items()}


def calc_deviation(
    portfolio_exp: dict[str, float],
    universe_exp: dict[str, float],
) -> dict[str, float]:
    """
    行业偏离度 = 持仓占比 - 策略占比。

    Returns:
        {"通信": 0.2, "新能源": -0.2, ...}
        正值 = 超配, 负值 = 低配
    """
    all_sectors = set(portfolio_exp.keys()) | set(universe_exp.keys())
    deviation = {}
    for s in all_sectors:
        p = portfolio_exp.get(s, 0.0)
        u = universe_exp.get(s, 0.0)
        deviation[s] = round(p - u, 3)
    return deviation


def calc_deviation_score(deviation: dict[str, float]) -> dict:
    """
    综合偏离评分 0-100。

    评分逻辑:
      - 行业重合度 (40分): portfolio 中的行业在 universe 中的覆盖率
      - 权重偏离度 (30分): 每行业差异平方和的倒数
      - 集中度风险 (30分): portfolio 中是否有过度集中 (>50%)

    注意: "未知" 行业不参与评分 (中性)
    """
    # 排除"未知"行业
    dev_filtered = {k: v for k, v in deviation.items() if k != "未知"}

    if not dev_filtered:
        return {"score": 50, "level": "⚪ 未知行业过高", "detail": {}}

    # 行业重合度
    shared = sum(1 for s, d in dev_filtered.items() if abs(d) < 0.3)
    all_sectors = len(dev_filtered)
    overlap_score = (shared / max(1, all_sectors)) * 40

    # 权重偏离
    total_dev = sum(d * d for d in dev_filtered.values())
    dev_score = max(0, 30 - total_dev * 50)

    # 集中度风险
    max_dev_abs = max(abs(d) for d in dev_filtered.values()) if dev_filtered else 0
    concentration_score = max(0, 30 - max_dev_abs * 60)

    score = round(overlap_score + dev_score + concentration_score, 1)

    if score >= 70:
        level = "🟢 正常"
    elif score >= 50:
        level = "🟡 注意"
    else:
        level = "🔴 警告"

    return {
        "score": score,
        "level": level,
        "detail": {
            "overlap": round(overlap_score, 1),
            "deviation_penalty": round(dev_score, 1),
            "concentration": round(concentration_score, 1),
        },
    }


def build_portfolio_report(
    holdings: list[dict],
    universe: list[str],
) -> dict:
    """
    统一输出接口 — 给 Streamlit 用。

    Args:
        holdings: [{"code": "600487"}, ...]
        universe: ["600487", "600522", ...]

    Returns:
        {
            "holdings": [...],           # 标准化持仓
            "portfolio_sectors": {...},  # 持仓行业分布
            "universe_sectors": {...},   # 策略行业分布
            "deviation": {...},          # 偏离雷达
            "deviation_score": {...},    # 综合评分
            "universe_size": N,
            "holdings_count": N,
        }
    """
    parsed = parse_holdings(holdings)
    portfolio_exp = calc_sector_exposure(parsed)
    universe_exp = calc_universe_exposure(universe)
    deviation = calc_deviation(portfolio_exp, universe_exp)
    score = calc_deviation_score(deviation)

    return {
        "holdings": parsed,
        "portfolio_sectors": portfolio_exp,
        "universe_sectors": universe_exp,
        "deviation": deviation,
        "deviation_score": score,
        "universe_size": len(universe),
        "holdings_count": len(holdings),
    }


def save_report(report: dict):
    """保存持仓分析报告"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, "portfolio_analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"持仓分析已保存 → {path}")


def print_report(report: dict):
    """控制台友好输出"""
    dev = report.get("deviation", {})
    score = report.get("deviation_score", {})

    print()
    print("─" * 50)
    print("  🧠 持仓 vs 策略 Universe 偏离分析")
    print("─" * 50)

    print(f"\n  📊 偏离评分: {score.get('score', 0)}/100 {score.get('level', '')}")

    if dev:
        print("\n  📈 行业偏离:")
        for s, d in sorted(dev.items(), key=lambda x: abs(x[1]), reverse=True):
            bar = "🔼" if d > 0 else "🔽" if d < 0 else "➖"
            print(f"    {bar} {s:8s}  {d:+.1%}")

    print(f"\n  📦 持仓: {report.get('holdings_count', 0)} 只")
    print(f"  🌐 Universe: {report.get('universe_size', 0)} 只")
    print("─" * 50)
