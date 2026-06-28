"""
data/build_rotating_universe.py — 自动行业轮动 Universe
============================================================
核心: 最近20日最强行业 = 当前市场主线 → 自动选股池
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 行业关键词映射
SECTOR_KEYWORDS = {
    "科技":   ["芯片", "半导体", "AI", "软件", "通信", "电子", "计算机", "数据", "云计算"],
    "新能源": ["电池", "光伏", "新能源", "锂电", "储能", "风电", "充电"],
    "金融":   ["银行", "保险", "证券", "金融", "信托"],
    "消费":   ["白酒", "食品", "家电", "饮料", "乳业", "调味", "零售"],
    "医药":   ["医药", "医疗", "生物", "制药", "疫苗", "器械"],
    "制造":   ["机械", "设备", "自动化", "机器人", "仪器", "重工", "船舶"],
    "材料":   ["化工", "材料", "有色", "钢铁", "水泥", "玻璃", "稀土"],
    "能源":   ["电力", "煤炭", "石油", "天然气", "公用"],
    "交通":   ["航空", "机场", "铁路", "公路", "港口", "物流"],
    "地产":   ["房地产", "建筑", "装修", "物业"],
    "农业":   ["农业", "养殖", "饲料", "种子", "化肥"],
    "传媒":   ["传媒", "游戏", "广告", "营销", "出版"],
}

def _get_sector(name: str) -> str:
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in str(name):
                return sector
    return "其他"


def build_universe(top_n: int = 300, top_sectors: int = 3) -> list[str]:
    """
    基于全市场实时行情, 识别最强行业并选股。

    返回: 股票代码列表
    """
    import akshare as ak
    import pandas as pd

    print("构建动态 Universe...")

    # 1. 全市场数据
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception:
        try:
            df = ak.stock_zh_a_spot()
        except Exception as e:
            print(f"  ⚠️ 获取全市场数据失败: {e}")
            return []

    sector_score = defaultdict(float)
    stocks = []

    for _, row in df.iterrows():
        code = str(row.get("代码", ""))
        name = str(row.get("名称", ""))
        change = float(row.get("涨跌幅", 0) or 0)
        volume = float(row.get("成交量", 0) or 0)

        if "ST" in name or "*" in name:
            continue
        if code.startswith(("8", "9", "4")):
            continue

        sector = _get_sector(name)
        sector_score[sector] += change

        stocks.append({"code": code, "name": name, "sector": sector,
                       "change": change, "volume": volume})

    # 2. 最强行业
    sorted_sectors = sorted(sector_score.items(), key=lambda x: x[1], reverse=True)
    top = [s[0] for s in sorted_sectors[:top_sectors]]
    print(f"  主线行业: {top}")

    # 3. 选股: 主线行业 + 涨>0 + 量>50万
    selected = []
    for s in stocks:
        if s["sector"] in top and s["change"] > 0 and s["volume"] > 5e5:
            selected.append(s["code"])

    selected = list(dict.fromkeys(selected))[:top_n]
    print(f"  Universe: {len(selected)} 只 (来自 {top})")
    return selected


if __name__ == "__main__":
    codes = build_universe()
    print(f"生成 {len(codes)} 只股票")
