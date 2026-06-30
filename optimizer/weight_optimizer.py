"""
optimizer/weight_optimizer.py — v3.0 权重自动优化器
=======================================================
基于因子 IC 自动调整因子权重, EMA 平滑防震荡

算法:
  new_weight = 0.7 * old_weight + 0.3 * (IC_i / sum(IC_all))
  IC 为负的因子权重降至 0.01 地板
"""
import json
import logging
import os

logger = logging.getLogger("v3.optimizer")

WEIGHTS_FILE = "data/weights.json"

# 默认权重 (rank_stocks 等价)
DEFAULT_WEIGHTS = {
    "momentum": 0.40,
    "price_value": 0.30,
    "volume": 0.20,
    "sector": 0.10,
}

# EMA 平滑系数
ALPHA = 0.3


def load_weights() -> dict:
    """读取当前权重"""
    if os.path.exists(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 初始化为默认值
    w = dict(DEFAULT_WEIGHTS)
    save_weights(w)
    return w


def save_weights(weights: dict):
    os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
    with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)
    logger.info(f"权重已保存: {weights}")


def optimize(factor_ic: dict[str, float]) -> dict:
    """
    根据因子 IC 更新权重。

    Args:
        factor_ic: {"momentum": 0.04, "volume": 0.02, "price_value": 0.01, "sector": -0.01}

    Returns:
        更新后的权重
    """
    old = load_weights()

    # IC 归一化: 取绝对值再归一化 (IC 为负代表反向预测力, 归零)
    ics = {k: max(0, v) for k, v in factor_ic.items() if k in old}
    total_ic = sum(ics.values())

    if total_ic <= 0:
        logger.warning("所有因子 IC ≤ 0, 保持当前权重")
        return old

    # IC 权重
    ic_weights = {k: v / total_ic for k, v in ics.items()}

    # EMA 平滑
    new = {}
    for k in old:
        ic_w = ic_weights.get(k, 0)
        new[k] = round((1 - ALPHA) * old[k] + ALPHA * ic_w, 4)

    # 地板: 单因子最低 0.01
    for k in new:
        new[k] = max(0.01, new[k])

    # 重新归一化
    total = sum(new.values())
    new = {k: round(v / total, 4) for k, v in new.items()}

    save_weights(new)

    print(f"🔧 权重更新:")
    for k in new:
        ic_val = factor_ic.get(k, 0)
        print(f"  {k:15s}: {old[k]:.2f} → {new[k]:.2f}  (IC={ic_val:+.4f})")

    return new


def get_scoring_weights() -> dict:
    """供 scoring 系统直接读取"""
    return load_weights()
