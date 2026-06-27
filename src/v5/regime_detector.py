"""
regime_engine.py — v5 市场状态识别 + 自适应策略切换系统
==========================================================
4大市场状态: 趋势市 / 震荡市 / 退潮市 / 恐慌市

v5 是整个系统的"总开关":
  - 判断市场状态 → 切换策略模式
  - 调整 v1-v4 权重和参数
  - 决定"该不该做交易"
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("quant-collector.regime")


# ============================================================
# 市场状态定义
# ============================================================

REGIME_TREND = "trend_market"        # 🟢 趋势市: 板块持续轮动, 高仓位
REGIME_RANGE = "range_market"        # 🟡 震荡市: 轮动快, 无主线, 中等仓位
REGIME_DOWNTREND = "downtrend_market" # 🔴 退潮市: 板块失败, 降仓防守
REGIME_CRASH = "crash_market"        # ⚫ 恐慌市: 快速下跌, 空仓

REGIME_ORDER = [REGIME_TREND, REGIME_RANGE, REGIME_DOWNTREND, REGIME_CRASH]

REGIME_LABELS = {
    REGIME_TREND: "趋势市",
    REGIME_RANGE: "震荡市",
    REGIME_DOWNTREND: "退潮市",
    REGIME_CRASH: "恐慌市",
}

# 状态 → 策略模式
REGIME_MODE = {
    REGIME_TREND: "aggressive_mode",
    REGIME_RANGE: "selective_mode",
    REGIME_DOWNTREND: "defensive_mode",
    REGIME_CRASH: "liquidation_mode",
}

# 状态 → 交易建议
REGIME_ACTION = {
    REGIME_TREND: "FULL_TRADE",
    REGIME_RANGE: "SELECTIVE_TRADE",
    REGIME_DOWNTREND: "REDUCE_ONLY",
    REGIME_CRASH: "NO_TRADE",
}

# 状态 → v1-v4 权重映射
REGIME_WEIGHTS = {
    REGIME_TREND: {
        "v1_signal_weight": 1.2,      # 信号激进
        "v3_leader_weight": 1.3,      # 主升浪最大化
        "v4_risk_limit": 0.85,        # 仓位上限高
        "allow_breakout": True,
        "allow_pullback": True,
        "min_sector_score": 6,
        "min_stock_score": 7,
    },
    REGIME_RANGE: {
        "v1_signal_weight": 1.0,
        "v3_leader_weight": 1.0,
        "v4_risk_limit": 0.55,        # 中等仓位
        "allow_breakout": False,       # 震荡不追突破
        "allow_pullback": True,        # 只做回踩
        "min_sector_score": 6,
        "min_stock_score": 7,
    },
    REGIME_DOWNTREND: {
        "v1_signal_weight": 0.7,
        "v3_leader_weight": 0.5,      # 主升信号降权
        "v4_risk_limit": 0.30,        # 低仓位
        "allow_breakout": False,
        "allow_pullback": True,        # 只防守
        "min_sector_score": 7,
        "min_stock_score": 8,
    },
    REGIME_CRASH: {
        "v1_signal_weight": 0.0,
        "v3_leader_weight": 0.0,
        "v4_risk_limit": 0.05,        # 接近空仓
        "allow_breakout": False,
        "allow_pullback": False,
        "min_sector_score": 9,
        "min_stock_score": 9,
    },
}


# ============================================================
# 5维 Regime Score
# ============================================================

def _score_index_trend(
    market: dict[str, Any],
    price_history: list[dict[str, Any]],
) -> tuple[float, str]:
    """
    Index Trend (0-3): 指数趋势方向
    - 20日均线方向
    - 主要指数涨跌
    """
    indices = market.get("indices", [])
    main_codes = {"000001", "399001", "000300"}
    main_returns = [idx.get("change_pct", 0) for idx in indices if idx.get("code") in main_codes]
    avg_return = sum(main_returns) / len(main_returns) if main_returns else 0

    # 多日趋势
    if len(price_history) >= 10:
        hist_returns = [
            h.get("overall_return", 0) for h in price_history[-10:]
            if h.get("overall_return", 0) is not None
        ]
        cum_10d = sum(hist_returns) if hist_returns else avg_return
        if avg_return > 1 and cum_10d > 0:
            return (3, "strong_up")
        elif avg_return > 0 and cum_10d > -1:
            return (2, "mild_up")
        elif avg_return > -1:
            return (1, "flat")
        else:
            return (0, "down")
    else:
        if avg_return > 1.5:
            return (3, "up_single")
        elif avg_return > 0:
            return (2, "flat_up")
        elif avg_return > -1.5:
            return (1, "flat_down")
        else:
            return (0, "down_single")


def _score_sector_breadth(
    cycle_data: dict[str, Any] | None,
    sectors_today: list[dict[str, Any]],
) -> tuple[float, str]:
    """
    Sector Breadth (0-3): 板块广度
    - ≥6分板块数量
    - 多板块共振程度
    """
    if not cycle_data:
        qualified = sum(
            1 for s in sectors_today
            if s.get("strength_score", 0) >= config.SECTOR_SCORE_QUALIFIED
        )
    else:
        snap = cycle_data.get("snapshot", {})
        qualified = snap.get("expansion_count", 0) + snap.get("confirm_count", 0) + snap.get("start_count", 0)

    if qualified >= 8:
        return (3, "broad")
    elif qualified >= 4:
        return (2, "moderate")
    elif qualified >= 1:
        return (1, "narrow")
    else:
        return (0, "none")


def _score_volume_expansion(
    market: dict[str, Any],
    price_history: list[dict[str, Any]],
) -> tuple[float, str]:
    """
    Volume Expansion (0-2): 成交量趋势
    - 持续放量 vs 缩量
    """
    vol_ratio = market.get("overall_volume_ratio", 1.0)

    if len(price_history) >= 5:
        hist_vols = [
            h.get("overall_volume_ratio", 1.0) for h in price_history[-5:]
            if h.get("overall_volume_ratio", 0) > 0
        ]
        avg_hist_vol = sum(hist_vols) / len(hist_vols) if hist_vols else 1.0
        if vol_ratio > 1.2 and vol_ratio > avg_hist_vol:
            return (2, "expanding")
        elif vol_ratio > 0.8:
            return (1, "stable")
        else:
            return (0, "contracting")
    else:
        if vol_ratio > 1.2:
            return (2, "expanding_single")
        elif vol_ratio > 0.8:
            return (1, "stable_single")
        else:
            return (0, "contracting_single")


def _score_leader_continuity(
    execute_data: dict[str, Any] | None,
    sentiment: dict[str, Any],
) -> tuple[float, str]:
    """
    Leader Continuity (0-2): 龙头连续性
    - v3 主升浪数量
    - 龙头是否断层
    """
    leaders = 0
    main_trend = 0
    if execute_data:
        summary = execute_data.get("summary", {})
        leaders = summary.get("leaders_found", 0)
        main_trend = summary.get("main_trend_count", 0)

    limit_up = sentiment.get("limit_up_count", 0)
    limit_down = sentiment.get("limit_down_count", 0)

    # 综合判断
    if main_trend >= 3 and limit_up > limit_down * 2:
        return (2, "strong_continuity")
    elif leaders >= 1 and limit_up > limit_down:
        return (1, "some_continuity")
    else:
        return (0, "broken")


def _score_risk_sentiment(
    sentiment: dict[str, Any],
    market: dict[str, Any],
) -> tuple[float, str]:
    """
    Risk Sentiment (0-2): 风险情绪
    - 涨跌停比例
    - 市场情绪等级
    - 下跌集中度
    """
    limit_up = sentiment.get("limit_up_count", 0)
    limit_down = sentiment.get("limit_down_count", 0)
    risk_level = sentiment.get("risk_level", "medium")
    up_down_ratio = sentiment.get("up_down_ratio", 1.0)

    score = 0
    label = "risky"

    # 涨跌停比
    if limit_down >= 100:
        return (0, "panic")  # 百股跌停
    if limit_up >= 80 and limit_down < 10:
        score = 2
        label = "euphoric"
    elif limit_up > limit_down * 3:
        score = 2
        label = "optimistic"
    elif limit_up > limit_down:
        score = 1
        label = "normal"
    elif limit_down > limit_up * 2:
        score = 0
        label = "fearful"
    else:
        score = 1
        label = "mixed"

    # 情绪等级修正
    if risk_level in ("extreme", "euphoric"):
        score = min(2, score + 1)
    elif risk_level == "high":
        score = max(0, score - 1)

    return (score, label)


# ============================================================
# 历史加载
# ============================================================

def _load_market_history(data_dir: str, target_date: str, lookback: int = 20) -> list[dict[str, Any]]:
    """加载市场级别历史 (overall_return + volume_ratio)"""
    hist = []
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    for offset in range(lookback, 0, -1):
        dt = target_dt - timedelta(days=offset)
        fp = Path(data_dir) / f"{dt.strftime('%Y-%m-%d')}.json"
        if not fp.exists():
            continue
        try:
            with open(fp) as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        mkt = d.get("market", {})
        hist.append({
            "overall_return": mkt.get("overall_return", 0),
            "overall_volume_ratio": mkt.get("overall_volume_ratio", 1.0),
            "market_status": mkt.get("market_status", "neutral"),
        })
    return hist


# ============================================================
# 主入口
# ============================================================

def analyze_regime(
    date_str: str,
    data_dir: str = config.DATA_DIR,
) -> dict[str, Any]:
    """
    v5 市场状态识别 + 策略切换。

    流程:
      1. 读取所有数据层
      2. 5维 Regime Score
      3. 判定市场状态
      4. 生成策略模式 + 权重
    """
    # 1. 读取数据
    data_path = Path(data_dir) / f"{date_str}.json"
    cycle_path = Path(data_dir) / f"{date_str}_cycle.json"
    execute_path = Path(data_dir) / f"{date_str}_execute.json"

    if not data_path.exists():
        return {"date": date_str, "error": "data_not_found", "version": "5.0.0"}

    with open(data_path, encoding="utf-8") as f:
        today_data = json.load(f)

    market = today_data.get("market", {})
    sectors = today_data.get("sectors", [])
    sentiment = today_data.get("sentiment", {})

    # 可选数据层
    cycle_data = None
    if cycle_path.exists():
        with open(cycle_path, encoding="utf-8") as f:
            cycle_data = json.load(f)

    execute_data = None
    if execute_path.exists():
        with open(execute_path, encoding="utf-8") as f:
            execute_data = json.load(f)

    # 2. 加载市场历史
    price_hist = _load_market_history(data_dir, date_str)

    # 3. 5维评分
    idx_score, idx_label = _score_index_trend(market, price_hist)
    breadth_score, breadth_label = _score_sector_breadth(cycle_data, sectors)
    vol_score, vol_label = _score_volume_expansion(market, price_hist)
    leader_score, leader_label = _score_leader_continuity(execute_data, sentiment)
    risk_score, risk_label = _score_risk_sentiment(sentiment, market)

    # 4. 总分 (0-12) → 归一化到 0-10
    raw_total = idx_score * 1.5 + breadth_score + vol_score + leader_score + risk_score * 1.5
    regime_score = round(min(10, max(0, raw_total * 10 / 12)), 1)

    # 5. 市场状态判定
    if regime_score >= 8:
        regime = REGIME_TREND
    elif regime_score >= 6:
        regime = REGIME_RANGE
    elif regime_score >= 4:
        regime = REGIME_DOWNTREND
    else:
        regime = REGIME_CRASH

    # 6. 策略模式 + 权重
    mode = REGIME_MODE[regime]
    action = REGIME_ACTION[regime]
    weights = REGIME_WEIGHTS[regime].copy()

    # 7. 建议
    recommendations = {
        REGIME_TREND: "主升浪活跃, 允许进攻, 可满仓策略",
        REGIME_RANGE: "板块轮动快, 只做回踩, 过滤弱突破",
        REGIME_DOWNTREND: "多数板块退潮, 降仓防守, 不做突破追高",
        REGIME_CRASH: "全线退潮, 流动性收缩, 空仓或极低仓位观察",
    }

    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "5.0.0",
        "market_regime": regime,
        "regime_label": REGIME_LABELS[regime],
        "regime_score": regime_score,
        "strategy_mode": mode,
        "action": action,
        "score_breakdown": {
            "index_trend": {"score": idx_score, "label": idx_label},
            "sector_breadth": {"score": breadth_score, "label": breadth_label},
            "volume_expansion": {"score": vol_score, "label": vol_label},
            "leader_continuity": {"score": leader_score, "label": leader_label},
            "risk_sentiment": {"score": risk_score, "label": risk_label},
        },
        "signals": {
            "v1_signal_weight": weights["v1_signal_weight"],
            "v3_leader_weight": weights["v3_leader_weight"],
            "v4_risk_limit": weights["v4_risk_limit"],
            "allow_breakout": weights["allow_breakout"],
            "allow_pullback": weights["allow_pullback"],
            "min_sector_score": weights["min_sector_score"],
            "min_stock_score": weights["min_stock_score"],
        },
        "recommendation": {
            "action": action,
            "comment": recommendations.get(regime, ""),
        },
        "snapshot": {
            "indices": {idx.get("code", ""): idx.get("change_pct", 0) for idx in market.get("indices", [])},
            "limit_up": sentiment.get("limit_up_count", 0),
            "limit_down": sentiment.get("limit_down_count", 0),
            "market_status": market.get("market_status", "unknown"),
        },
    }

    logger.info(
        f"市场状态: {REGIME_LABELS[regime]}({regime_score}), "
        f"模式{mode}, {action}"
    )
    return result
