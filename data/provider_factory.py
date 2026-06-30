"""
data/provider_factory.py — 可插拔数据源工厂
===============================================
统一接口, 主源失败自动切备源。
新增数据源只需实现 DataProvider 接口并注册即可。

用法:
    factory = ProviderFactory()
    df = factory.fetch_history("000001")  # 自动主→备切换
"""
import logging
import time
from typing import Protocol

logger = logging.getLogger("v3.provider")

# ═══════════════════════════════════════════
# 接口定义 — 新增数据源必须实现这个
# ═══════════════════════════════════════════

class DataProvider(Protocol):
    """数据源协议: 所有 provider 必须实现 fetch_history"""
    name: str

    def fetch_history(self, code: str, start_date: str = "20240101") -> "pd.DataFrame | None":
        """返回日线 DataFrame (列: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率)"""
        ...


# ═══════════════════════════════════════════
# Provider 1: AKShare (东方财富, 主源)
# ═══════════════════════════════════════════

class AKShareProvider:
    name = "akshare"

    def fetch_history(self, code: str, start_date: str = "20240101"):
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start_date, adjust="qfq")
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"AKShare [{code}]: {e}")
        return None


# ═══════════════════════════════════════════
# Provider 2: Baostock (备用, 免费无需token)
# ═══════════════════════════════════════════

class BaostockProvider:
    name = "baostock"

    def fetch_history(self, code: str, start_date: str = "20240101"):
        try:
            import baostock as bs
            import pandas as pd

            # 转换代码格式: sh600183 → sh.600183, bj920564 → bj.920564
            # Universe 中代码格式: shXXXXXX / bjXXXXXX / szXXXXXX / 纯数字XXXXXX
            raw = str(code)
            # 去掉可能的前缀
            for prefix in ["sh", "sz", "bj"]:
                if raw.startswith(prefix) and len(raw) == len(prefix) + 6:
                    bs_code = f"{prefix}.{raw[len(prefix):]}"
                    break
            else:
                # 纯数字, 推断市场
                if raw.startswith(("8", "4")):
                    bs_code = f"bj.{raw}"
                elif raw.startswith(("6", "5", "9")):
                    bs_code = f"sh.{raw}"
                else:
                    bs_code = f"sz.{raw}"

            lg = bs.login()
            if lg is None or lg.error_code != "0":
                bs.logout()
                return None

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,close,high,low,volume,amount,amplitude,pctChg,change,turn",
                start_date=start_date,
                frequency="d",
                adjustflag="2",  # 前复权
            )
            if rs is None or rs.error_code != "0":
                err = rs.error_msg if rs else "无响应"
                bs.logout()
                return None

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            bs.logout()

            if not data_list:
                return None

            df = pd.DataFrame(data_list, columns=rs.fields)
            # 列名对齐 AKShare 格式
            df = df.rename(columns={
                "date": "日期", "open": "开盘", "close": "收盘",
                "high": "最高", "low": "最低", "volume": "成交量",
                "amount": "成交额", "amplitude": "振幅",
                "pctChg": "涨跌幅", "change": "涨跌额", "turn": "换手率",
            })
            # 转数值
            for col in ["开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            return df if not df.empty else None

        except ImportError:
            logger.warning("baostock 未安装, 跳过备源")
            return None
        except Exception as e:
            logger.warning(f"Baostock [{code}]: {e}")
            try:
                import baostock as bs
                bs.logout()
            except Exception:
                pass
            return None


# ═══════════════════════════════════════════
# Provider Factory — 自动切换
# ═══════════════════════════════════════════

class ProviderFactory:
    """可插拔数据源工厂"""

    def __init__(self):
        self.providers: list[DataProvider] = []
        # 按优先级注册
        self.register(AKShareProvider())
        self.register(BaostockProvider())

    def register(self, provider: DataProvider):
        """注册数据源 (后注册的优先级低)"""
        self.providers.append(provider)
        logger.info(f"注册数据源: {provider.name}")

    def fetch_history(self, code: str, start_date: str = "20240101",
                      retries: int = 1) -> "pd.DataFrame | None":
        """
        按优先级尝试所有数据源, 主源失败自动切备源。
        每个源最多试 retries+1 次, 失败后静默切换下一个源。
        """
        for provider in self.providers:
            for attempt in range(retries + 1):
                try:
                    df = provider.fetch_history(code, start_date)
                    if df is not None and not df.empty:
                        if provider.name != self.providers[0].name:
                            logger.info(f"备源 {provider.name} 成功: {code}")
                        return df
                except Exception:
                    pass
                if attempt < retries:
                    time.sleep(1.5)
        return None

    @property
    def primary_name(self) -> str:
        return self.providers[0].name if self.providers else "none"


# 全局单例
_factory: ProviderFactory | None = None


def get_factory() -> ProviderFactory:
    global _factory
    if _factory is None:
        _factory = ProviderFactory()
    return _factory
