"""
main.py — 数据采集编排入口
============================
按顺序执行各模块, 模块间容错, 降级机制, 标准化 JSON 输出

使用:
    python main.py              # 采集今日数据
    python main.py --date 2026-06-27  # 采集指定日期
    python main.py --check-only       # 仅校验已有数据
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from src.utils import setup_logging, is_trading_day
from src.market import fetch_index_quotes, compute_market_summary
from src.sector import fetch_industry_sectors
from src.stock import fetch_stock_quotes, detect_anomalies_from_stocks
from src.sentiment import fetch_hot_stocks, compute_sentiment_indicators
from src.validator import validate_data

logger = logging.getLogger("quant-collector")


def collect_all(date_str: str) -> dict[str, Any]:
    """
    执行完整数据采集流程。

    Args:
        date_str: 日期字符串 YYYY-MM-DD

    Returns:
        完整的标准化数据字典
    """
    result = {
        "date": date_str,
        "generated_at": datetime.now(config.CN_TZ).isoformat(),
        "version": "1.0.0",
    }

    errors = []
    warnings = []

    # ============================================================
    # 1. 大盘数据 (腾讯财经 — 稳定, 不依赖其他模块)
    # ============================================================
    logger.info("=" * 50)
    logger.info(f"开始采集市场数据: {date_str}")
    logger.info("=" * 50)

    logger.info("[1/4] 大盘指数数据...")
    try:
        indices = fetch_index_quotes()
        market_summary = compute_market_summary(indices)
        result["market"] = {
            "indices": indices,
            **market_summary,
        }
        logger.info(f"  大盘: {market_summary['market_status']}, "
                    f"涨跌 {market_summary['overall_return']}%")
    except Exception as e:
        logger.error(f"大盘数据采集失败: {e}")
        errors.append(f"market: {e}")
        result["market"] = {
            "indices": [],
            "overall_return": 0.0,
            "overall_volume_ratio": 1.0,
            "market_status": "unknown",
        }

    # ============================================================
    # 2. 板块数据 (东财 push2 — 可能因反爬失败, 降级处理)
    # ============================================================
    logger.info("[2/4] 行业板块数据...")
    sectors = []
    try:
        sectors = fetch_industry_sectors()
    except Exception as e:
        logger.warning(f"板块数据采集失败 (降级): {e}")
        warnings.append(f"sector: {e}")

    result["sectors"] = sectors

    # ============================================================
    # 3. 个股数据 (腾讯财经批量 — 稳定但需分批)
    # ============================================================
    logger.info(f"[3/4] 个股数据 ({len(config.STOCK_POOL)} 只)...")
    stocks = []
    try:
        stocks = fetch_stock_quotes()
    except Exception as e:
        logger.error(f"个股数据采集失败: {e}")
        errors.append(f"stock: {e}")

    result["stocks"] = stocks

    # ============================================================
    # 4. 情绪指标 (同花顺 + 自计算)
    # ============================================================
    logger.info("[4/4] 情绪指标...")
    sentiment = {}
    try:
        hot_stocks = fetch_hot_stocks(date_str)
    except Exception as e:
        logger.warning(f"同花顺热点获取失败 (降级): {e}")
        hot_stocks = []

    try:
        sentiment = compute_sentiment_indicators(
            stocks=stocks,
            sectors=sectors,
            hot_stocks=hot_stocks,
        )
    except Exception as e:
        logger.error(f"情绪指标计算失败: {e}")
        errors.append(f"sentiment: {e}")
        sentiment = {
            "limit_up_count": 0,
            "limit_down_count": 0,
            "up_down_ratio": 1.0,
            "risk_level": "unknown",
            "top_themes": [],
            "anomalies": [],
        }

    # 合并个股异常事件
    try:
        stock_anomalies = detect_anomalies_from_stocks(stocks)
        sentiment.setdefault("anomalies", []).extend(stock_anomalies)
    except Exception as e:
        logger.warning(f"异常检测失败: {e}")

    result["sentiment"] = sentiment

    # ============================================================
    # 5. 数据校验
    # ============================================================
    logger.info("数据校验...")
    try:
        quality = validate_data(result["market"], sectors, stocks, sentiment)
        result["data_quality"] = quality["data_quality"]
        result["quality_issues"] = quality.get("issues", [])
        result["quality_metrics"] = quality.get("metrics", {})
    except Exception as e:
        logger.error(f"数据校验失败: {e}")
        result["data_quality"] = "error"
        result["quality_issues"] = [{"severity": "error", "message": str(e)}]
        result["quality_metrics"] = {}

    # ============================================================
    # 6. 汇总
    # ============================================================
    result["collection_errors"] = errors
    result["collection_warnings"] = warnings

    active_stocks = sum(1 for s in stocks if not s.get("is_suspended", True))
    logger.info("=" * 50)
    logger.info(f"采集完成: 指数{len(result['market']['indices'])}个, "
                f"板块{len(sectors)}个, 个股{active_stocks}只活跃")
    logger.info(f"数据质量: {result['data_quality']}, "
                f"错误{len(errors)}个, 警告{len(warnings)}个")
    logger.info("=" * 50)

    return result


def save_result(result: dict[str, Any], output_path: str | None = None) -> str:
    """保存结果到 JSON 文件"""
    if output_path is None:
        output_path = f"{config.DATA_DIR}/{result['date']}.json"

    # 确保目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(output_path)
    logger.info(f"数据已写入: {output_path} ({file_size/1024:.1f} KB)")
    return output_path


def main() -> int:
    """主入口，返回退出码: 0=正常, 1=有warning, 2=严重错误"""
    setup_logging()

    # 解析参数
    date_str = config.today_cn()
    check_only = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--check-only":
            check_only = True
            i += 1
        elif args[i] == "--help":
            print("用法: python main.py [--date YYYY-MM-DD] [--check-only]")
            print("  --date        指定日期 (默认今天)")
            print("  --check-only  仅检查是否为交易日")
            return 0
        else:
            i += 1

    # 交易日检查
    if not is_trading_day(date_str):
        logger.info(f"{date_str} 不是交易日, 跳过数据采集")
        # 非交易日不报错, 退出码0
        return 0

    if check_only:
        logger.info(f"{date_str} 是交易日")
        return 0

    # 执行采集
    start_time = time.time()
    result = collect_all(date_str)
    elapsed = time.time() - start_time

    # 保存
    output_path = save_result(result)
    logger.info(f"总耗时: {elapsed:.1f}s")

    # 退出码
    quality = result.get("data_quality", "ok")
    if quality == "error":
        return 2
    elif quality == "warning":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
