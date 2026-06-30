"""
core/data_registry.py — CSV 统一调度层 v3.0
=============================================================
所有回测强制通过此层访问数据, 不再直接读文件
v3 新增: OHLCV 归一化、日期索引、前瞻收益计算、多股对齐

DataRegistry:
  · 索引全部 data/raw/daily/*.csv
  · get_all() → 全部代码
  · get(code) → 单只 DataFrame (原始列名)
  · get_ohlcv(code) → 归一化 DataFrame [date,open,high,low,close,volume]
  · get_batch(codes) → 批量 {code: DataFrame}
  · get_prices(codes) → 批量 {code: [close prices]}
  · get_forward_returns(code, dates, horizons) → 前瞻收益
  · get_aligned_prices(codes, start, end) → 对齐收盘价矩阵
  · stats() → 注册表统计
"""
import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger("v3.registry")

DATA_DIR = "data/raw/daily"

# 中英文列名映射 (兼容两种表头)
_COL_MAP = {
    "日期": "date", "date": "date",
    "股票代码": "code", "code": "code",
    "开盘": "open", "open": "open",
    "收盘": "close", "close": "close",
    "最高": "high", "high": "high",
    "最低": "low", "low": "low",
    "成交量": "volume", "volume": "volume",
    "成交额": "amount", "amount": "amount",
    "振幅": "amplitude", "amplitude": "amplitude",
    "涨跌幅": "pct", "pct": "pct",
    "涨跌额": "change", "change": "change",
    "换手率": "turnover", "turnover": "turnover",
}


class DataRegistry:
    """统一数据入口 — 系统只有一个 Registry 实例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        self.files = self._scan()
        self.index: dict[str, pd.DataFrame] = {}
        self._bad: list[str] = []

    def _scan(self) -> list[str]:
        if not os.path.exists(DATA_DIR):
            return []
        return sorted(f.replace(".csv", "") for f in os.listdir(DATA_DIR) if f.endswith(".csv"))

    def reload(self) -> None:
        """重新扫描并构建索引"""
        self.files = self._scan()
        self.index.clear()
        self._bad.clear()

    def get_all(self) -> list[str]:
        return list(self.files)

    def get(self, code: str) -> pd.DataFrame | None:
        if code in self.index:
            return self.index[code]
        path = f"{DATA_DIR}/{code}.csv"
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            self.index[code] = df
            return df
        except Exception as e:
            self._bad.append(code)
            logger.warning(f"Bad CSV: {code} {e}")
            return None

    def get_batch(self, codes: list[str]) -> dict[str, pd.DataFrame]:
        """批量加载 DataFrame"""
        result = {}
        for c in codes:
            df = self.get(c)
            if df is not None:
                result[c] = df
        return result

    def get_prices(self, codes: list[str]) -> dict[str, list[float]]:
        """批量加载收盘价序列 (用于快速回测)"""
        result = {}
        for c in codes:
            df = self.get(c)
            if df is not None and not df.empty:
                col = "close" if "close" in df.columns else "收盘"
                if col in df.columns:
                    result[c] = [float(v) for v in df[col].values]
        return result

    # ── v3.0 新增方法 ──

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一列名为英文, 兼容中英两种表头, 返回 [date,open,high,low,close,volume]"""
        result = df.rename(columns=_COL_MAP)
        keep_cols = [c for c in ["date", "open", "high", "low", "close", "volume"]
                     if c in result.columns]
        result = result[keep_cols].copy()
        if "date" in result.columns:
            result["date"] = pd.to_datetime(result["date"])
            result = result.sort_values("date").reset_index(drop=True)
        return result

    def get_ohlcv(self, code: str) -> pd.DataFrame | None:
        """归一化 OHLCV DataFrame, date 为索引"""
        df = self.get(code)
        if df is None or df.empty:
            return None
        ndf = self._normalize(df)
        if ndf.empty:
            return None
        ndf = ndf.set_index("date")
        return ndf

    def get_forward_returns(
        self, code: str, signal_dates: list[str],
        horizons: list[int] | None = None,
    ) -> dict:
        """
        计算信号在指定日期后的前瞻收益。

        Args:
            code: 股票代码
            signal_dates: 信号日期列表 ["2026-06-15", ...]
            horizons: 期限列表 [1, 5, 10, 20]

        Returns:
            {signal_date: {ret_1d: 0.015, ret_5d: 0.032, ...}, ...}
        """
        if horizons is None:
            horizons = [1, 5, 10, 20]
        ndf = self.get_ohlcv(code)
        if ndf is None or ndf.empty:
            return {}
        closes = ndf["close"]
        dates = [d for d in closes.index if isinstance(d, pd.Timestamp) or hasattr(d, 'strftime')]
        results = {}
        for sd_str in signal_dates:
            try:
                sd = pd.Timestamp(sd_str)
            except Exception:
                continue
            if sd not in closes.index:
                continue
            pos = closes.index.get_loc(sd)
            entry_px = float(closes.iloc[pos])
            rets = {}
            for h in horizons:
                fwd = pos + h
                if fwd < len(closes):
                    exit_px = float(closes.iloc[fwd])
                    rets[f"ret_{h}d"] = round((exit_px / entry_px - 1), 4) if entry_px > 0 else None
                else:
                    rets[f"ret_{h}d"] = None
            results[sd_str] = rets
        return results

    def get_aligned_prices(
        self, codes: list[str],
        start: str | None = None, end: str | None = None,
    ) -> pd.DataFrame:
        """
        多股日期对齐的收盘价矩阵 (DateFrame: index=date, columns=code)

        Args:
            codes: 股票代码列表
            start/end: 日期范围 "2026-01-01" 或 None=全部

        Returns:
            对齐后的 close 价格 DataFrame
        """
        frames = {}
        for c in codes[:50]:  # 限制 50 只防内存爆炸
            ndf = self.get_ohlcv(c)
            if ndf is not None and not ndf.empty:
                frames[c] = ndf["close"]
        if not frames:
            return pd.DataFrame()
        result = pd.DataFrame(frames)
        if start:
            result = result[result.index >= pd.Timestamp(start)]
        if end:
            result = result[result.index <= pd.Timestamp(end)]
        return result.dropna(how="all")

    # ── v2 原有方法 ──

    def stats(self) -> dict[str, Any]:
        loaded = len(self.index)
        total = len(self.files)
        return {
            "total_csv": total,
            "loaded_into_memory": loaded,
            "bad_files": len(self._bad),
            "coverage_pct": round(loaded / max(1, total) * 100, 1),
            "sample": self.files[:5],
        }

    def print_manifest(self) -> None:
        s = self.stats()
        logger.info(f"Registry: {s['total_csv']} CSV, {s['loaded_into_memory']} 已加载, "
                    f"{s['bad_files']} 损坏")
        print(f"📦 DataRegistry: {s['total_csv']} CSV → {s['loaded_into_memory']} 就绪 "
              f"({s['coverage_pct']}%)")
