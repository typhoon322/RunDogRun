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
import os
import threading
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
# Provider 1: 东方财富 HTTP (直接调API, 不依赖AKShare)
# ═══════════════════════════════════════════

class EastMoneyProvider:
    """直接调东方财富 HTTP API, 绕过 AKShare 的网络问题"""
    name = "eastmoney"

    def fetch_history(self, code: str, start_date: str = "20240101"):
        try:
            import requests
            import pandas as pd

            # 纯数字代码
            raw = str(code)
            for prefix in ["sh", "sz", "bj"]:
                if raw.startswith(prefix) and len(raw) == len(prefix) + 6:
                    raw = raw[len(prefix):]
                    break

            # 判断市场
            if raw.startswith(("6", "5", "9")):
                secid = f"1.{raw}"
            else:
                secid = f"0.{raw}"

            # 日期格式转换: 20240101 → 20240101
            beg = start_date.replace("-", "") if "-" in start_date else start_date

            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                f"?secid={secid}&klt=101&fqt=1"
                f"&beg={beg}&end=20991231"
                f"&fields1=f1,f2,f3,f4,f5,f6"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            )

            resp = requests.get(url, timeout=8,
                               headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if data.get("rc") != 0 or not data.get("data"):
                return None

            klines = data["data"].get("klines", [])
            if not klines:
                return None

            rows = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 11:
                    rows.append({
                        "日期": parts[0],
                        "开盘": float(parts[1]) if parts[1] != "-" else None,
                        "收盘": float(parts[2]) if parts[2] != "-" else None,
                        "最高": float(parts[3]) if parts[3] != "-" else None,
                        "最低": float(parts[4]) if parts[4] != "-" else None,
                        "成交量": float(parts[5]) if parts[5] != "-" else None,
                        "成交额": float(parts[6]) if parts[6] != "-" else None,
                        "振幅": float(parts[7]) if parts[7] != "-" else None,
                        "涨跌幅": float(parts[8]) if parts[8] != "-" else None,
                        "涨跌额": float(parts[9]) if parts[9] != "-" else None,
                        "换手率": float(parts[10]) if parts[10] != "-" else None,
                    })

            if not rows:
                return None
            return pd.DataFrame(rows)

        except Exception:
            return None


# ═══════════════════════════════════════════
# Provider 3: 新浪财经 HTTP (免费, 无需token)
# ═══════════════════════════════════════════

class SinaProvider:
    """新浪财经日K线接口"""
    name = "sina"

    def fetch_history(self, code: str, start_date: str = "20240101"):
        try:
            import requests
            import pandas as pd

            raw = str(code)
            for prefix in ["sh", "sz", "bj"]:
                if raw.startswith(prefix) and len(raw) == len(prefix) + 6:
                    raw = raw[len(prefix):]
                    break

            # 新浪代码格式: sh600000, sz000001
            if raw.startswith(("6", "5", "9")):
                sina_code = f"sh{raw}"
            else:
                sina_code = f"sz{raw}"

            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale=240&ma=no&datalen=1023"
            resp = requests.get(url, timeout=8,
                               headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            if not data:
                return None

            rows = []
            for d in data:
                dt = d.get("day", "")
                if dt < start_date.replace("-", ""):
                    continue
                rows.append({
                    "日期": dt,
                    "开盘": float(d.get("open", 0) or 0),
                    "收盘": float(d.get("close", 0) or 0),
                    "最高": float(d.get("high", 0) or 0),
                    "最低": float(d.get("low", 0) or 0),
                    "成交量": float(d.get("volume", 0) or 0),
                    "成交额": 0.0,
                    "振幅": 0.0,
                    "涨跌幅": 0.0,
                    "涨跌额": 0.0,
                    "换手率": 0.0,
                })
            return pd.DataFrame(rows) if rows else None
        except Exception:
            return None


# ═══════════════════════════════════════════
# Provider 4: 腾讯财经 HTTP (免费, 无需token)
# ═══════════════════════════════════════════

class TencentProvider:
    """腾讯财经日K线接口"""
    name = "tencent"

    def fetch_history(self, code: str, start_date: str = "20240101"):
        try:
            import requests
            import pandas as pd

            raw = str(code)
            for prefix in ["sh", "sz", "bj"]:
                if raw.startswith(prefix) and len(raw) == len(prefix) + 6:
                    raw = raw[len(prefix):]
                    break

            if raw.startswith(("6", "5", "9")):
                tx_code = f"sh{raw}"
            else:
                tx_code = f"sz{raw}"

            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tx_code},day,,,1023,qfq"
            resp = requests.get(url, timeout=8,
                               headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            klines = data.get("data", {}).get(tx_code, {}).get("qfqday") or \
                     data.get("data", {}).get(tx_code, {}).get("day")
            if not klines:
                return None

            rows = []
            for d in klines:
                dt = d[0]
                if dt < start_date.replace("-", ""):
                    continue
                rows.append({
                    "日期": dt,
                    "开盘": float(d[1]),
                    "收盘": float(d[2]),
                    "最高": float(d[3]),
                    "最低": float(d[4]),
                    "成交量": float(d[5]),
                    "成交额": 0.0,
                    "振幅": 0.0,
                    "涨跌幅": 0.0,
                    "涨跌额": 0.0,
                    "换手率": 0.0,
                })
            return pd.DataFrame(rows) if rows else None
        except Exception:
            return None


# ═══════════════════════════════════════════
# Provider 5: AKShare (兜底)
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
            import os as _os  # 防御性: 部分 Linux 环境 baostock 内部可能污染命名空间

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
        self._fail_count: dict[str, int] = {}  # 熔断计数器
        # 按优先级注册 (先注册=主源)
        self.register(EastMoneyProvider())   # 主源: 直连东方财富HTTP (8s超时)
        self.register(SinaProvider())         # 备源2: 新浪财经 (8s超时)
        self.register(TencentProvider())      # 备源3: 腾讯财经 (8s超时)
        # AKShare: 仅在本地环境启用 (GitHub Actions 上持续 RemoteDisconnected)
        if not os.environ.get("GITHUB_ACTIONS"):
            self.register(AKShareProvider())
        # Baostock: GH Actions 上 login/logout 每次调用太慢, 跳过
        if not os.environ.get("GITHUB_ACTIONS"):
            self.register(BaostockProvider())

    def register(self, provider: DataProvider):
        """注册数据源 (后注册的优先级低)"""
        self.providers.append(provider)
        logger.info(f"注册数据源: {provider.name}")

    def fetch_history(self, code: str, start_date: str = "20240101",
                      retries: int = 0) -> "pd.DataFrame | None":
        """
        按优先级尝试所有数据源, 主源失败自动切备源。
        每个源只试1次 (retries=0), 快速失败快速切换。
        """
        for provider in self.providers:
            # 熔断: 连续失败3次的 provider 跳过
            if self._fail_count.get(provider.name, 0) >= 3:
                continue
            try:
                df = provider.fetch_history(code, start_date)
                if df is not None and not df.empty:
                    self._fail_count[provider.name] = 0  # 重置
                    if provider.name != self.providers[0].name:
                        logger.info(f"备源 {provider.name} 成功: {code}")
                    return df
                else:
                    self._fail_count[provider.name] = self._fail_count.get(provider.name, 0) + 1
            except Exception:
                self._fail_count[provider.name] = self._fail_count.get(provider.name, 0) + 1
        return None

    @property
    def primary_name(self) -> str:
        return self.providers[0].name if self.providers else "none"


# 全局单例 (线程安全)
_factory: ProviderFactory | None = None
_factory_lock = threading.Lock()


def get_factory() -> ProviderFactory:
    global _factory
    if _factory is None:
        with _factory_lock:
            if _factory is None:
                _factory = ProviderFactory()
    return _factory
