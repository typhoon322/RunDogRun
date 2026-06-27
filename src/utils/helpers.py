"""
量化中线数据采集系统 v1 — 工具层
提供: 东财节流 / HTTP重试 / 安全转换 / 交易日判断
"""

import time
import random
import logging
import functools
from datetime import datetime, timedelta
from typing import Any, Callable

import requests

import config

logger = logging.getLogger("quant-collector")

# ============================================================
# 东财防封: 全局节流 + 会话复用
# ============================================================

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
_em_last_call = 0.0


def em_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = config.HTTP_TIMEOUT,
    **kwargs,
) -> requests.Response:
    """
    东财统一请求入口: 自动节流 + 复用 session + 默认 UA。
    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。
    """
    global _em_last_call
    wait = config.EM_MIN_INTERVAL - (time.time() - _em_last_call)
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, config.EM_MAX_JITTER))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call = time.time()


# ============================================================
# HTTP 通用重试 + 超时控制
# ============================================================

def retry_request(
    request_func: Callable[[], requests.Response],
    max_retries: int = config.MAX_RETRIES,
    backoff: float = config.RETRY_BACKOFF,
    label: str = "",
) -> requests.Response | None:
    """
    通用 HTTP 重试机制，指数退避。

    Args:
        request_func: 返回 requests.Response 的无参可调用对象
        max_retries: 最大重试次数
        backoff: 退避因子(秒)
        label: 日志标签

    Returns:
        成功返回 Response，全部失败返回 None
    """
    for attempt in range(max_retries + 1):
        try:
            resp = request_func()
            if resp.status_code == 200:
                return resp
            if 400 <= resp.status_code < 500:
                # 客户端错误不重试
                logger.warning(
                    f"[{label}] HTTP {resp.status_code}, 客户端错误, 不重试"
                )
                return resp
            logger.warning(
                f"[{label}] HTTP {resp.status_code}, 第{attempt+1}次尝试"
            )
        except requests.RequestException as e:
            logger.warning(f"[{label}] 请求异常: {e}, 第{attempt+1}次尝试")

        if attempt < max_retries:
            sleep_time = backoff * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)

    logger.error(f"[{label}] 全部 {max_retries+1} 次尝试均失败")
    return None


# ============================================================
# 安全数值转换
# ============================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float，失败返回默认值"""
    if value is None or value == "" or value == "-":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int，失败返回默认值"""
    if value is None or value == "" or value == "-":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


# ============================================================
# 交易日判断
# ============================================================

# 中国法定节假日 (2026 年已知的主要假期 — 需每年更新)
_CN_HOLIDAYS_2026 = {
    # 元旦
    "2026-01-01", "2026-01-02",
    # 春节 (2026-02-17 除夕)
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    # 清明节
    "2026-04-06",
    # 劳动节
    "2026-05-01", "2026-05-04", "2026-05-05",
    # 端午节
    "2026-06-19",
    # 中秋节
    "2026-09-25",
    # 国庆节
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
}

# 已知调休工作日 (周六/周日上班)
_CN_WORK_SATURDAYS_2026 = {
    # 春节补班
    "2026-02-14",  # 周六上班
    "2026-02-28",  # 周六上班
    # 五一补班
    "2026-04-25",  # 周六上班
    # 十一补班
    "2026-09-19",  # 周六上班
    "2026-10-10",  # 周六上班
}


def is_trading_day(date_str: str | None = None) -> bool:
    """
    判断是否为 A 股交易日。

    规则: 周一至周五 且 非法定节假日（含调休后的实际休市日）
    注: 此函数不包含盘中临时停市场景
    """
    if date_str is None:
        date_str = config.today_cn()

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False

    # 周末
    if dt.weekday() >= 5:  # 5=周六, 6=周日
        # 调休工作日 (周六/周日上班)
        if date_str in _CN_WORK_SATURDAYS_2026:
            return True
        return False

    # 法定节假日 (周一至周五的假期)
    if date_str in _CN_HOLIDAYS_2026:
        return False

    return True


# ============================================================
# 日志配置
# ============================================================

def setup_logging(level: int = logging.INFO) -> None:
    """配置结构化日志"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ============================================================
# 辅助函数
# ============================================================

def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """将列表分割为固定大小的批次"""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]
