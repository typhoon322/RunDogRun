"""
main.py — 量化系统 v8 入口
============================
用法:
    python main.py                    # 完整管道 v1→v8 → data/outputs/latest.json
    python main.py --date YYYY-MM-DD  # 指定日期
    python main.py --backtest         # v7 回测
    python main.py --train            # v8 RL Agent 训练
"""
from src.core.pipeline import run as run_pipeline

if __name__ == "__main__":
    result = run_pipeline()
    path = result.save("data/outputs/latest.json")
    print("DONE:", result.summary())
    print("OUTPUT:", path)
