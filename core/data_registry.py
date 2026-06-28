"""
core/data_registry.py — CSV 统一调度层 (Data Registry)
=============================================================
所有回测强制通过此层访问数据, 不再直接读文件

DataRegistry:
  · 索引全部 data/raw/daily/*.csv
  · get_all() → 全部代码
  · get(code) → 单只 DataFrame
  · get_batch(codes) → 批量 {code: DataFrame}
  · get_prices(codes) → 批量 {code: [close prices]}
  · stats() → 注册表统计
"""
import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger("v2.registry")

DATA_DIR = "data/raw/daily"


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
