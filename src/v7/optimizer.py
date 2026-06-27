"""
optimizer.py — v7 参数优化 + 防过拟合
======================================
Grid Search + Walk-Forward Validation
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("quant.v7.optimizer")


# 可优化参数空间
PARAM_GRID = {
    "SECTOR_SCORE_QUALIFIED": [5, 6, 7],
    "STOCK_SCORE_CANDIDATE": [6, 7, 8],
    "SIGNAL_BREAKOUT_VOL_RATIO": [1.3, 1.5, 1.8],
    "POSITION_MAX_SINGLE": [0.20, 0.25, 0.30],
    "POSITION_MAX_COUNT": [3, 5, 7],
    "STOP_LOSS_PCT": [-0.08, -0.10, -0.12],
}


def grid_search(
    start_date: str,
    end_date: str,
    data_dir: str = "data",
) -> dict[str, Any]:
    """
    简化网格搜索: 测试关键参数组合。

    完整版会测试所有组合，这里用采样方式。
    """
    from src.v7.backtest_engine import run_backtest

    best_score = -999
    best_params = {}
    results = []

    # 采样核心组合 (不测全部 3^6=729 组合)
    combos = _sample_combos()
    logger.info(f"参数优化: {len(combos)} 个组合")

    for combo in combos:
        # 临时修改参数
        _apply_params(combo)
        bt = run_backtest(start_date, end_date, data_dir)
        if "error" in bt:
            continue
        score = bt.get("metrics", {}).get("strategy_score", 0)
        results.append({"params": combo, "score": score, "metrics": bt["metrics"]})
        if score > best_score:
            best_score = score
            best_params = combo

    # 恢复默认
    _restore_defaults()

    return {
        "best_params": best_params,
        "best_score": best_score,
        "tested": len(results),
        "top_5": sorted(results, key=lambda x: x["score"], reverse=True)[:5],
    }


def walk_forward_validation(
    data_dir: str = "data",
    train_months: int = 6,
    test_months: int = 2,
) -> dict[str, Any]:
    """
    滚动窗口验证: 训练→测试→滑动。

    检测策略是否在不同时段表现一致。
    """
    from src.v7.backtest_engine import run_backtest

    # 获取数据日期范围
    days = sorted([f.stem for f in Path(data_dir).glob("????-??-??.json")])
    if len(days) < 60:
        return {"error": "insufficient_data", "days": len(days)}

    windows = []
    train_start = datetime.strptime(days[0], "%Y-%m-%d")
    total_end = datetime.strptime(days[-1], "%Y-%m-%d")

    current = train_start
    results = []
    while current < total_end:
        train_end = current + timedelta(days=train_months * 30)
        test_end = min(train_end + timedelta(days=test_months * 30), total_end)

        train_start_s = current.strftime("%Y-%m-%d")
        train_end_s = train_end.strftime("%Y-%m-%d")
        test_end_s = test_end.strftime("%Y-%m-%d")

        try:
            bt = run_backtest(train_end_s, test_end_s, data_dir)
            if "error" not in bt:
                results.append({
                    "train": f"{train_start_s}→{train_end_s}",
                    "test": f"{train_end_s}→{test_end_s}",
                    "return": bt["metrics"].get("total_return_pct", 0),
                    "score": bt["metrics"].get("strategy_score", 0),
                })
        except Exception as e:
            logger.warning(f"窗口 {train_end_s}→{test_end_s} 失败: {e}")

        current = test_end

    # 分析一致性
    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    score_std = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5 if scores else 0

    is_robust = score_std < 15 and avg_score >= 50

    return {
        "windows": results,
        "window_count": len(results),
        "avg_score": round(avg_score, 1),
        "score_std": round(score_std, 1),
        "is_robust": is_robust,
        "overfit_risk": "LOW" if is_robust else ("HIGH" if score_std > 25 else "MEDIUM"),
    }


def _sample_combos() -> list[dict]:
    """采样关键参数组合"""
    combos = []
    for sq in [6, 7]:
        for sc in [7, 8]:
            for vol in [1.3, 1.5]:
                for size in [0.25, 0.30]:
                    for cnt in [3, 5]:
                        for sl in [-0.08, -0.10]:
                            combos.append({
                                "SECTOR_SCORE_QUALIFIED": sq,
                                "STOCK_SCORE_CANDIDATE": sc,
                                "SIGNAL_BREAKOUT_VOL_RATIO": vol,
                                "POSITION_MAX_SINGLE": size,
                                "POSITION_MAX_COUNT": cnt,
                                "STOP_LOSS_PCT": sl,
                            })
    return combos[:64]  # 限制64个


def _apply_params(params: dict) -> None:
    import config
    for k, v in params.items():
        if hasattr(config, k):
            setattr(config, k, v)


def _restore_defaults() -> None:
    import config
    config.SECTOR_SCORE_QUALIFIED = 6
    config.STOCK_SCORE_CANDIDATE = 7
    config.SIGNAL_BREAKOUT_VOL_RATIO = 1.5
    config.POSITION_MAX_SINGLE = 0.30
    config.POSITION_MAX_COUNT = 5
    config.STOP_LOSS_PCT = -0.10
