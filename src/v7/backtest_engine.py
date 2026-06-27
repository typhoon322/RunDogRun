"""
backtest_engine.py — v7 回测引擎核心
=====================================
模拟 v1-v6 系统在历史数据上的完整交易表现
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("quant.v7.backtest")


def run_backtest(
    start_date: str,
    end_date: str,
    data_dir: str = config.DATA_DIR,
) -> dict[str, Any]:
    """
    对历史区间进行完整回测。

    流程:
      for each trading day:
        1. 运行 v1-v6 pipeline
        2. 模拟交易执行
        3. 记录持仓/收益/回撤
    """
    trades: list[dict] = []
    daily_values = [1.0]  # 净值序列
    positions: dict[str, dict] = {}
    cash = 1.0

    trading_days = _get_trading_days(data_dir, start_date, end_date)

    if len(trading_days) < 5:
        return {"error": "insufficient_data", "days": len(trading_days)}

    logger.info(f"回测: {start_date} → {end_date}, {len(trading_days)} 交易日")

    for date_str in trading_days:
        # 读取当日信号
        trade_path = Path(data_dir) / f"{date_str}_trade.json"
        cycle_path = Path(data_dir) / f"{date_str}_cycle.json"
        regime_path = Path(data_dir) / f"{date_str}_regime.json"

        signals = _load_signals(trade_path)
        regime = _load_regime(regime_path)
        cycle = _load_cycle(cycle_path)

        # 更新持仓 (检查卖出信号)
        _process_exits(positions, signals, date_str, trades)

        # 开新仓 (检查买入信号 + 风控限制)
        _process_entries(positions, signals, regime, cycles=cycle, cash=cash,
                         date_str=date_str, trades=trades)

        # 计算当日净值
        portfolio_value = cash + _positions_value(positions, date_str, data_dir)
        daily_values.append(portfolio_value)

        # 止损检查
        _check_stop_loss(positions, date_str, trades, data_dir)

    # 计算最终指标
    metrics = compute_metrics(daily_values, trades)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "trading_days": len(trading_days),
        "total_trades": len(trades),
        "metrics": metrics,
        "trades": trades[-50:],  # 最近50笔
        "equity_curve": daily_values[-90:],  # 最近90天
    }


def _get_trading_days(data_dir: str, start: str, end: str) -> list[str]:
    """获取区间内所有有数据文件的日期"""
    days = []
    dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while dt <= end_dt:
        ds = dt.strftime("%Y-%m-%d")
        if (Path(data_dir) / f"{ds}.json").exists():
            days.append(ds)
        dt += timedelta(days=1)
    return days


def _load_signals(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    result = {}
    for p in data.get("positions", []):
        code = p.get("code", "")
        result[code] = p
    return result


def _load_regime(path: Path) -> dict:
    if not path.exists():
        return {"market_regime": "neutral"}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"market_regime": "neutral"}


def _load_cycle(path: Path) -> dict:
    if not path.exists():
        return {"market_cycle": "neutral"}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"market_cycle": "neutral"}


def _process_exits(positions: dict, signals: dict, date_str: str, trades: list) -> None:
    """处理卖出"""
    to_remove = []
    for code, pos in positions.items():
        sig = signals.get(code, {})
        action = sig.get("action", "")
        if action in ("SELL", "EMPTY"):
            sell_price = sig.get("price", pos.get("entry_price", 0))
            entry_price = pos.get("entry_price", sell_price)
            trade_return = (sell_price - entry_price) / entry_price if entry_price > 0 else 0

            trades.append({
                "date": date_str, "code": code, "name": sig.get("name", ""),
                "action": "SELL", "entry_date": pos.get("entry_date", ""),
                "entry_price": entry_price, "exit_price": sell_price,
                "return_pct": round(trade_return * 100, 2),
                "hold_days": _hold_days(pos.get("entry_date", ""), date_str),
                "reason": sig.get("reason", ""),
            })
            to_remove.append(code)

    for code in to_remove:
        del positions[code]


def _process_entries(positions: dict, signals: dict, regime: dict, cycles: dict,
                     cash: float, date_str: str, trades: list) -> None:
    """处理买入"""
    max_positions = 5
    risk_limit = 0.7
    if regime.get("market_regime") == "downtrend_market":
        risk_limit = 0.3
    elif regime.get("market_regime") == "crash_market":
        risk_limit = 0.0

    used = len(positions)
    for code, sig in signals.items():
        if used >= max_positions:
            break
        if code in positions:
            continue
        action = sig.get("action", "")
        if action not in ("BUY", "ENTRY"):
            continue
        size = min(sig.get("position_size", 0.1), risk_limit / max(1, max_positions))
        entry_price = sig.get("price", 0)
        if entry_price <= 0:
            continue

        positions[code] = {
            "entry_date": date_str, "entry_price": entry_price,
            "size": size, "name": sig.get("name", ""),
        }
        trades.append({
            "date": date_str, "code": code, "name": sig.get("name", ""),
            "action": "BUY", "entry_price": entry_price, "size": round(size, 2),
            "signal_type": sig.get("signal_type", ""), "signal_grade": sig.get("signal_grade", ""),
        })
        used += 1


def _positions_value(positions: dict, date_str: str, data_dir: str) -> float:
    """计算持仓市值"""
    total = 0.0
    data_path = Path(data_dir) / f"{date_str}.json"
    if not data_path.exists():
        return total
    try:
        with open(data_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return total

    stock_prices = {s["code"]: s.get("price", 0) for s in data.get("stocks", [])}
    for code, pos in positions.items():
        cur_price = stock_prices.get(code, pos["entry_price"])
        total += pos["size"] * (cur_price / pos["entry_price"]) if pos["entry_price"] > 0 else 0
    return total


def _check_stop_loss(positions: dict, date_str: str, trades: list, data_dir: str) -> None:
    """止损检查"""
    to_remove = []
    for code, pos in list(positions.items()):
        data_path = Path(data_dir) / f"{date_str}.json"
        if not data_path.exists():
            continue
        try:
            with open(data_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for s in data.get("stocks", []):
            if s["code"] == code:
                cur = s.get("price", 0)
                entry = pos["entry_price"]
                if entry > 0 and cur / entry - 1 <= -0.10:
                    trades.append({
                        "date": date_str, "code": code,
                        "action": "STOP_LOSS", "return_pct": round((cur/entry-1)*100, 2),
                    })
                    to_remove.append(code)
                break
    for code in to_remove:
        positions.pop(code, None)


def _hold_days(entry: str, exit_: str) -> int:
    if not entry:
        return 0
    try:
        d1 = datetime.strptime(entry, "%Y-%m-%d")
        d2 = datetime.strptime(exit_, "%Y-%m-%d")
        return (d2 - d1).days
    except (ValueError, TypeError):
        return 0


def compute_metrics(daily_values: list[float], trades: list[dict]) -> dict[str, Any]:
    """计算完整评估指标"""
    n = len(daily_values)
    if n < 2:
        return {"error": "insufficient_data"}

    values = daily_values
    # 收益
    total_return = round((values[-1] - values[0]) / values[0] * 100, 1)
    peak = max(values)
    drawdowns = [(v - peak) / peak * 100 for v in values]
    max_dd = round(min(drawdowns), 1)

    # 年化
    days = len(values) - 1
    if days > 0:
        annual_return = round(((values[-1] / values[0]) ** (252 / days) - 1) * 100, 1)
    else:
        annual_return = 0.0

    # 胜率
    sell_trades = [t for t in trades if t.get("action") in ("SELL", "STOP_LOSS")]
    wins = sum(1 for t in sell_trades if t.get("return_pct", 0) > 0)
    win_rate = round(wins / len(sell_trades), 2) if sell_trades else 0.0

    # 盈亏比
    avg_win = sum(t.get("return_pct", 0) for t in sell_trades if t.get("return_pct", 0) > 0) / max(1, wins)
    losses = [t.get("return_pct", 0) for t in sell_trades if t.get("return_pct", 0) <= 0]
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_factor = round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 99.0

    # 连亏
    max_consecutive_losses = 0
    current_streak = 0
    for t in sell_trades:
        if t.get("return_pct", 0) <= 0:
            current_streak += 1
            max_consecutive_losses = max(max_consecutive_losses, current_streak)
        else:
            current_streak = 0

    # 夏普
    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    avg_r = sum(returns) / len(returns) if returns else 0
    variance = sum((r - avg_r) ** 2 for r in returns) / len(returns) if returns else 1e-9
    sharpe = round((avg_r / (variance ** 0.5)) * (252 ** 0.5), 2) if variance > 0 else 0

    # 策略评分
    strategy_score = _compute_strategy_score(total_return, max_dd, win_rate, profit_factor, sharpe)

    return {
        "total_return_pct": total_return,
        "annual_return_pct": annual_return,
        "max_drawdown_pct": max_dd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_consecutive_losses,
        "sharpe_ratio": sharpe,
        "total_trades": len(sell_trades),
        "strategy_score": strategy_score,
        "strategy_status": _score_to_status(strategy_score),
    }


def _compute_strategy_score(total_return: float, max_dd: float, win_rate: float,
                            profit_factor: float, sharpe: float) -> int:
    """综合策略评分 0-100"""
    # 收益质量 (0-30)
    return_score = min(30, max(0, int(total_return / 3)))
    # 风险稳定性 (0-25)
    risk_score = min(25, max(0, int((15 + max_dd) / 15 * 25))) if max_dd > -15 else 25
    # 一致性 (0-20)
    consistency = min(20, int(win_rate * 20))
    # 稳健性 (0-15)
    robustness = min(15, int(profit_factor * 5)) if profit_factor < 3 else 15
    # 效率 (0-10)
    efficiency = min(10, max(0, int(sharpe * 5)))
    return return_score + risk_score + consistency + robustness + efficiency


def _score_to_status(score: int) -> str:
    if score >= 80:
        return "TRADE_READY"
    elif score >= 60:
        return "OPTIMIZABLE"
    elif score >= 40:
        return "STRUCTURAL_ISSUE"
    else:
        return "UNUSABLE"
