"""
trade_executor.py — v3 + v4 终极执行层
========================================
v3: 龙头生命周期系统 (Leader Lifecycle)
v4: 资金管理 + 回撤控制系统 (Risk & Capital)

一句话: v3 负责赚钱(吃主升浪), v4 负责不死(控制回撤)
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("quant-collector.executor")


# ============================================================
# v3: 龙头生命周期定义
# ============================================================

LC_ACCUMULATION = "accumulation"    # 启动期: 低位放量, 首次突破
LC_TEST = "test"                    # 试盘期: 回踩不破, 洗盘
LC_MAIN_TREND = "main_trend"        # 主升期: 趋势明确, 板块共振 🔥
LC_ACCELERATION = "acceleration"    # 加速期: 连续大阳, 放量突破
LC_CLIMAX = "climax"                # 高潮期: 巨量, 高波动
LC_DISTRIBUTION = "distribution"    # 震荡期: 横盘, 分歧加大
LC_COLLAPSE = "collapse"            # 结束期: 跌破支撑, 放量下跌

LC_ORDER = [
    LC_ACCUMULATION, LC_TEST, LC_MAIN_TREND,
    LC_ACCELERATION, LC_CLIMAX, LC_DISTRIBUTION, LC_COLLAPSE,
]

LC_LABELS = {
    LC_ACCUMULATION: "启动期", LC_TEST: "试盘期",
    LC_MAIN_TREND: "主升期", LC_ACCELERATION: "加速期",
    LC_CLIMAX: "高潮期", LC_DISTRIBUTION: "震荡期", LC_COLLAPSE: "结束期",
}

# 生命周期 → 动作映射
LC_ACTION = {
    LC_ACCUMULATION: "BUY_TRIAL",      # 小仓试错
    LC_TEST: "ADD",                    # 逐步加仓
    LC_MAIN_TREND: "HOLD_CORE",        # 核心持仓
    LC_ACCELERATION: "HOLD",           # 持有不加仓
    LC_CLIMAX: "REDUCE",               # 减仓
    LC_DISTRIBUTION: "SELL",           # 清仓
    LC_COLLAPSE: "EMPTY",              # 空仓
}

# 生命周期 → 仓位映射
LC_POSITION = {
    LC_ACCUMULATION: (0.10, 0.20),
    LC_TEST: (0.20, 0.40),
    LC_MAIN_TREND: (0.40, 0.80),
    LC_ACCELERATION: (0.20, 0.50),  # 持有但不加
    LC_CLIMAX: (0.05, 0.15),
    LC_DISTRIBUTION: (0.0, 0.0),
    LC_COLLAPSE: (0.0, 0.0),
}


# ============================================================
# v4: 风险状态机
# ============================================================

RISK_AGGRESSIVE = "aggressive"
RISK_NORMAL = "normal"
RISK_DEFENSIVE = "defensive"
RISK_LIQUIDATION = "liquidation"

# 市场状态 → 总仓位上限
MARKET_EXPOSURE = {
    "risk_on": (0.70, 0.90),
    "neutral": (0.40, 0.70),
    "risk_off": (0.00, 0.40),
}

# 回撤 → 动作
DRAWDOWN_ACTIONS = [
    (-0.05, "reduce_20", "降仓20%"),
    (-0.10, "reduce_50", "降仓50%"),
    (-0.15, "liquidate", "空仓观察"),
]


# ============================================================
# 历史加载
# ============================================================

def _load_price_history(data_dir: str, target_date: str, code: str, lookback: int = 30) -> list[dict]:
    """加载单只股票多日价格历史"""
    hist = []
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    for offset in range(lookback, 0, -1):
        dt = target_dt - timedelta(days=offset)
        fp = Path(data_dir) / f"{dt.strftime('%Y-%m-%d')}.json"
        if not fp.exists():
            continue
        try:
            with open(fp) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for s in data.get("stocks", []):
            if s.get("code") == code:
                hist.append(s)
                break
    return hist


# ============================================================
# v3: 龙头评分
# ============================================================

def compute_leader_score(
    stock: dict[str, Any],
    sector_cycle: dict[str, Any] | None,
    price_history: list[dict[str, Any]],
    hot_stocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    5维龙头评分 (0-10):

    Relative Strength (0-3):   跑赢板块程度
    Trend Strength (0-2):      趋势力度
    Volume Persistence (0-2):  量能持续性
    Breakout Quality (0-2):    突破质量
    Market Attention (0-1):    市场关注度
    """
    # 1. Relative Strength (0-3)
    rs = stock.get("relative_strength", 0)
    if rs >= 2:
        rs_score = 3
    elif rs >= 1:
        rs_score = 2
    elif rs >= 0:
        rs_score = 1
    else:
        rs_score = 0

    # 2. Trend Strength (0-2): 多日涨幅 + 连阳天数
    ret = stock.get("return", 0)
    up_days = 0
    if price_history:
        for h in reversed(price_history[-5:]):
            if h.get("return", 0) > 0:
                up_days += 1
            else:
                break
    if ret > 3 and up_days >= 3:
        trend_score = 2
    elif ret > 0 and up_days >= 1:
        trend_score = 1
    else:
        trend_score = 0

    # 3. Volume Persistence (0-2)
    vol = stock.get("volume_ratio", 1.0)
    vol_up_days = 0
    if price_history:
        for h in reversed(price_history[-5:]):
            if h.get("volume_ratio", 1.0) > 1.0:
                vol_up_days += 1
            else:
                break
    if vol > 1.5 and vol_up_days >= 2:
        vol_score = 2
    elif vol > 1.0:
        vol_score = 1
    else:
        vol_score = 0

    # 4. Breakout Quality (0-2)
    price = stock.get("price", 0)
    high = stock.get("high", 0)
    prev_high = 0
    if len(price_history) >= 5:
        prev_highs = [h.get("high", 0) for h in price_history[-6:-1]]
        prev_high = max(prev_highs) if prev_highs else high
    if price >= prev_high and vol > 1.3 and ret > 1:
        breakout_score = 2
    elif price >= prev_high * 0.97:
        breakout_score = 1
    else:
        breakout_score = 0

    # 5. Market Attention (0-1): 是否在同花顺热点中
    attention_score = 0
    if hot_stocks:
        code = stock.get("code", "")
        for hs in hot_stocks:
            if hs.get("code") == code:
                attention_score = 1
                break

    total = rs_score + trend_score + vol_score + breakout_score + attention_score

    return {
        "relative_strength_score": rs_score,
        "trend_strength_score": trend_score,
        "volume_persistence_score": vol_score,
        "breakout_quality_score": breakout_score,
        "market_attention_score": attention_score,
        "leader_score": total,
    }


# ============================================================
# v3: 生命周期判定
# ============================================================

def classify_lifecycle(
    stock: dict[str, Any],
    leader_scores: dict[str, Any],
    sector_cycle: dict[str, Any] | None,
    price_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    判定龙头生命周期阶段。
    """
    score = leader_scores.get("leader_score", 0)
    ret = stock.get("return", 0)
    vol = stock.get("volume_ratio", 1.0)
    price = stock.get("price", 0)
    sec_stage = sector_cycle.get("cycle_stage", "") if sector_cycle else ""

    # 计算 MA20
    prices = [h.get("price", 0) for h in price_history if h.get("price", 0) > 0]
    if price > 0:
        prices.append(price)
    ma20 = sum(prices[-20:]) / min(20, len(prices)) if prices else price
    above_ma = price >= ma20 * 0.98 if ma20 > 0 else True

    # 连阳/连阴
    up_streak = 0
    down_streak = 0
    for h in reversed(price_history[-10:]):
        if h.get("return", 0) > 0:
            if down_streak == 0:
                up_streak += 1
            else:
                break
        else:
            if up_streak == 0:
                down_streak += 1
            else:
                break

    # 判定逻辑
    if ret < -3 and vol > 1.5 and not above_ma:
        stage = LC_COLLAPSE
    elif abs(ret) < 1 and vol < 0.7 and down_streak >= 2 and sec_stage in ("divergence",):
        stage = LC_DISTRIBUTION
    elif ret > 5 and vol > 2.5 and up_streak >= 3:
        stage = LC_CLIMAX if sec_stage not in ("expansion",) else LC_ACCELERATION
    elif ret > 3 and vol > 1.3 and up_streak >= 3 and above_ma and score >= 7:
        stage = LC_ACCELERATION if sec_stage == "expansion" else LC_MAIN_TREND
    elif ret > 0 and above_ma and score >= 6 and sec_stage in ("expansion", "confirm"):
        stage = LC_MAIN_TREND
    elif ret > -2 and above_ma and vol < 1.2 and score >= 5:
        stage = LC_TEST
    elif score >= 4 and sec_stage in ("start", "confirm"):
        stage = LC_ACCUMULATION
    elif not above_ma and down_streak >= 3:
        stage = LC_COLLAPSE
    else:
        stage = LC_TEST  # 默认中性

    action = LC_ACTION.get(stage, "HOLD")
    pos_range = LC_POSITION.get(stage, (0.0, 0.0))

    return {
        "life_cycle_stage": stage,
        "life_cycle_label": LC_LABELS.get(stage, "未知"),
        "action": action,
        "position_range": pos_range,
        "above_ma20": above_ma,
        "up_streak": up_streak,
        "down_streak": down_streak,
    }


# ============================================================
# v4: 回撤控制
# ============================================================

def compute_drawdown(
    positions_history: list[dict[str, Any]],
    current_positions_value: float = 1.0,
) -> dict[str, Any]:
    """
    计算账户回撤状态。

    positions_history: [{date, total_value}, ...]
    """
    if not positions_history:
        return {"drawdown_pct": 0.0, "peak_value": current_positions_value, "action": "hold"}

    values = [h.get("total_value", 1.0) for h in positions_history]
    values.append(current_positions_value)
    peak = max(values)
    drawdown = (current_positions_value - peak) / peak if peak > 0 else 0

    action = "hold"
    action_label = "正常"
    for threshold, act, label in reversed(DRAWDOWN_ACTIONS):
        if drawdown <= threshold:
            action = act
            action_label = label
            break

    return {
        "drawdown_pct": round(drawdown * 100, 1),
        "peak_value": round(peak, 4),
        "current_value": round(current_positions_value, 4),
        "action": action,
        "action_label": action_label,
    }


def determine_risk_mode(
    drawdown: float,
    consecutive_losses: int,
    market_state: str,
) -> str:
    """
    风险状态机: AGGRESSIVE → NORMAL → DEFENSIVE → LIQUIDATION
    """
    if drawdown <= -0.15:
        return RISK_LIQUIDATION
    if drawdown <= -0.10 or consecutive_losses >= 5:
        return RISK_DEFENSIVE
    if drawdown <= -0.05 or consecutive_losses >= 3:
        return RISK_DEFENSIVE
    if market_state == "risk_off":
        return RISK_DEFENSIVE
    if market_state == "risk_on" and drawdown >= -0.02 and consecutive_losses == 0:
        return RISK_AGGRESSIVE
    return RISK_NORMAL


# ============================================================
# v4: 动态仓位引擎
# ============================================================

def calculate_position_size(
    lifecycle: dict[str, Any],
    market_state: str,
    risk_mode: str,
    drawdown: float,
) -> tuple[float, str]:
    """
    综合计算最终仓位。

    三重约束:
      1. 生命周期仓位区间
      2. 市场状态总仓位上限
      3. 风险模式折扣
    """
    pos_range = lifecycle.get("position_range", (0.0, 0.0))
    action = lifecycle.get("action", "HOLD")
    stage = lifecycle.get("life_cycle_stage", "")

    # 卖出信号 → 0
    if action in ("SELL", "EMPTY", "REDUCE"):
        if action == "SELL" or action == "EMPTY":
            return (0.0, f"{action}: 清仓")
        return (pos_range[0] * 0.3, f"{action}: 降仓至{pos_range[0]*0.3:.0%}")

    # 生命周期基准仓位 (取中位数)
    lifecycle_base = (pos_range[0] + pos_range[1]) / 2

    # 市场状态折扣
    market_range = MARKET_EXPOSURE.get(market_state, (0.40, 0.70))
    market_max = market_range[1] if risk_mode == RISK_AGGRESSIVE else market_range[0]
    if risk_mode == RISK_DEFENSIVE:
        market_max *= 0.5
    elif risk_mode == RISK_LIQUIDATION:
        market_max = 0.0

    # 回撤折扣
    drawdown_discount = 1.0
    if drawdown <= -0.10:
        drawdown_discount = 0.5
    elif drawdown <= -0.05:
        drawdown_discount = 0.8

    # 最终仓位
    final_size = lifecycle_base * drawdown_discount
    final_size = min(final_size, market_max, config.POSITION_MAX_SINGLE)
    final_size = max(final_size, 0.0)

    reason = f"lifecycle={lifecycle_base:.0%} × dd={drawdown_discount:.1f} → {final_size:.0%}"

    return (round(final_size, 2), reason)


# ============================================================
# 持仓历史追踪
# ============================================================

def _load_account_history(data_dir: str) -> dict[str, Any]:
    """读取账户历史 (用于回撤计算)"""
    fp = Path(data_dir) / "account_history.json"
    if fp.exists():
        try:
            with open(fp) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"daily_values": [], "total_trades": 0, "consecutive_losses": 0}


def _save_account_history(data_dir: str, history: dict[str, Any]) -> None:
    fp = Path(data_dir) / "account_history.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ============================================================
# 主入口: 终极执行分析
# ============================================================

def execute(
    date_str: str,
    data_dir: str = config.DATA_DIR,
) -> dict[str, Any]:
    """
    v3+v4 终极执行分析。

    流程:
      1. 读取所有数据层 (采集/评分/周期)
      2. 对候选股进行龙头评分 + 生命周期判定
      3. 组合资金管理 + 回撤控制
      4. 输出最终执行建议
    """
    # 1. 读取数据
    data_path = Path(data_dir) / f"{date_str}.json"
    watchlist_path = Path(data_dir) / f"{date_str}_watchlist.json"
    cycle_path = Path(data_dir) / f"{date_str}_cycle.json"

    if not data_path.exists():
        return {"date": date_str, "error": "data_not_found", "version": "4.0.0"}

    with open(data_path, encoding="utf-8") as f:
        today_data = json.load(f)

    sector_cycles = {}
    market_state = "neutral"
    if cycle_path.exists():
        with open(cycle_path, encoding="utf-8") as f:
            cycle_data = json.load(f)
        for sc in cycle_data.get("sector_cycles", []):
            sector_cycles[sc["name"]] = sc
        market_state = cycle_data.get("market_state", "neutral")

    candidates = {}
    if watchlist_path.exists():
        with open(watchlist_path, encoding="utf-8") as f:
            watchlist = json.load(f)
        for c in watchlist.get("candidates", []):
            candidates[c["code"]] = c

    # 2. 获取同花顺热点
    hot_stocks_raw = today_data.get("sentiment", {}).get("top_themes", [])
    hot_codes = set()
    for theme in hot_stocks_raw:
        # themes are {name, count} — we don't have individual hot stock codes here
        pass
    # Actually, the hot stocks are in the sentiment data from the original fetch
    # Let's use a different approach: check if stock is in top performers
    sentiment = today_data.get("sentiment", {})

    # 3. 加载账户历史 && v4 全局风险判定
    account_hist = _load_account_history(data_dir)
    daily_values = account_hist.get("daily_values", [])
    consecutive_losses = account_hist.get("consecutive_losses", 0)
    current_value = daily_values[-1].get("total_value", 1.0) if daily_values else 1.0
    drawdown_info = compute_drawdown(daily_values, current_value)
    risk_mode = determine_risk_mode(
        drawdown_info["drawdown_pct"] / 100,
        consecutive_losses,
        market_state,
    )

    max_allowed = MARKET_EXPOSURE.get(market_state, (0.40, 0.70))[1]
    if risk_mode == RISK_DEFENSIVE:
        max_allowed *= 0.5
    elif risk_mode == RISK_LIQUIDATION:
        max_allowed = 0.0

    # 4. 对每个候选股进行分析
    leaders = []
    all_stocks = {s["code"]: s for s in today_data.get("stocks", [])}

    for code, candidate in candidates.items():
        stock = all_stocks.get(code)
        if not stock:
            continue

        sec_name = stock.get("sector", "")
        sec_cycle = sector_cycles.get(sec_name)

        # 注入score (from analyzer)
        stock["score"] = candidate.get("score", 0)
        stock["relative_strength"] = candidate.get("relative_strength", 0)
        stock["rank_in_sector"] = candidate.get("rank_in_sector", 99)

        # 加载价格历史
        price_hist = _load_price_history(data_dir, date_str, code)

        # v3: 龙头评分
        leader_scores = compute_leader_score(stock, sec_cycle, price_hist)

        # v3: 生命周期
        lifecycle = classify_lifecycle(stock, leader_scores, sec_cycle, price_hist)

        # v4: 仓位计算 (使用全局 risk_mode)
        pos_size, pos_reason = calculate_position_size(
            lifecycle, market_state, risk_mode, drawdown_info["drawdown_pct"] / 100
        )

        leaders.append({
            "code": code,
            "name": stock.get("name", ""),
            "sector": sec_name,
            "sector_cycle": sec_cycle.get("cycle_stage", "") if sec_cycle else "",
            "leader_score": leader_scores["leader_score"],
            "leader_breakdown": {
                k: v for k, v in leader_scores.items() if k != "leader_score"
            },
            "life_cycle_stage": lifecycle["life_cycle_stage"],
            "life_cycle_label": lifecycle["life_cycle_label"],
            "action": lifecycle["action"],
            "position_size": pos_size,
            "position_reason": pos_reason,
            "return": stock.get("return", 0),
            "volume_ratio": stock.get("volume_ratio", 0),
            "price": stock.get("price", 0),
        })

    # 排序: leader_score 降序
    leaders.sort(key=lambda x: x["leader_score"], reverse=True)

    # 5. 总体风险控制
    total_exposure = sum(l["position_size"] for l in leaders if l["position_size"] > 0)
    max_allowed = MARKET_EXPOSURE.get(market_state, (0.40, 0.70))[1]
    if risk_mode == RISK_DEFENSIVE:
        max_allowed *= 0.5
    elif risk_mode == RISK_LIQUIDATION:
        max_allowed = 0.0

    # 超出上限则按比例缩仓
    if total_exposure > max_allowed and max_allowed > 0:
        scale = max_allowed / total_exposure
        for l in leaders:
            l["position_size"] = round(l["position_size"] * scale, 2)
        total_exposure = max_allowed

    # 6. 更新持仓历史 (模拟)
    daily_values.append({
        "date": date_str,
        "total_value": round(current_value * (1 + total_exposure * 0.01), 4),  # 简化模拟
    })
    account_hist["daily_values"] = daily_values[-90:]  # 保留90天
    _save_account_history(data_dir, account_hist)

    # 7. 组装输出
    top_leader = leaders[0] if leaders else None

    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "4.0.0",
        "market_state": market_state,
        "risk_mode": risk_mode,
        "leader_stock": _format_leader(top_leader),
        "all_positions": [_format_leader(l) for l in leaders[:5]],
        "risk_control": {
            "market_state": market_state,
            "risk_mode": risk_mode,
            "total_exposure": round(total_exposure, 2),
            "max_allowed_exposure": round(max_allowed, 2),
            "drawdown": drawdown_info["drawdown_pct"],
            "drawdown_action": drawdown_info.get("action_label", "hold"),
            "consecutive_losses": consecutive_losses,
        },
        "summary": {
            "total_candidates": len(candidates),
            "leaders_found": len(leaders),
            "main_trend_count": sum(1 for l in leaders if l["life_cycle_stage"] == LC_MAIN_TREND),
            "accumulation_count": sum(1 for l in leaders if l["life_cycle_stage"] in (LC_ACCUMULATION, LC_TEST)),
        },
    }

    logger.info(
        f"执行分析: {len(leaders)}个龙头, "
        f"主升{result['summary']['main_trend_count']}, "
        f"总仓位{total_exposure:.0%}, 模式{risk_mode}"
    )
    return result


def _format_leader(leader: dict[str, Any] | None) -> dict[str, Any] | None:
    if not leader:
        return None
    fields = [
        "code", "name", "sector", "sector_cycle",
        "leader_score", "life_cycle_stage", "life_cycle_label",
        "action", "position_size", "position_reason",
        "return", "volume_ratio", "price",
    ]
    return {k: leader.get(k) for k in fields}
