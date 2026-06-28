"""
app.py — v2.5 策略监控仪表盘
================================
Streamlit UI → 自动读取 Git 仓库数据 → 手机可访问
"""
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="v2.5 Monitor", page_icon="📊", layout="wide")
st.title("📊 v2.5 策略监控仪表盘")
st.caption(f"自动更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ═══════════════════════════════════════════════
# 数据资产: 直接从 Git 仓库读取 (Streamlit Cloud 可用)
# ═══════════════════════════════════════════════
csv_dir = "data/raw/daily"
csv_count = len(os.listdir(csv_dir)) if os.path.exists(csv_dir) else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("CSV 数据仓库", f"{csv_count} 只", delta="Git 同步")
col2.metric("Registry", "✅ 在线" if os.path.exists("data/registry.json") else "⚠ 待同步")
col3.metric("日报", "✅" if os.path.exists("data/outputs/daily_report.json") else "❌")
col4.metric("Pipeline", "✅" if os.path.exists("data/outputs/pipeline_log.json") else "❌")

# ═══════════════════════════════════════════════
# Pipeline 状态 (如果有日志)
# ═══════════════════════════════════════════════
if os.path.exists("data/outputs/pipeline_log.json"):
    with open("data/outputs/pipeline_log.json") as f:
        plog = json.load(f)
    steps = plog.get("steps", [])
    with st.expander("🔧 Pipeline 执行详情"):
        c = st.columns(3)
        c[0].metric("总步骤", plog.get("total", 0))
        c[1].metric("✅ OK", plog.get("ok_count", 0))
        c[2].metric("❌ Fail", plog.get("fail_count", 0))
        for s in steps[-8:]:
            icon = {"ok": "✅", "fail": "❌", "skip": "⏭"}.get(s["status"], "❓")
            st.caption(f"{icon} `{s['step']}`  {s.get('detail','')}  ({s.get('time','')})")

# ═══════════════════════════════════════════════
# 日报数据
# ═══════════════════════════════════════════════
report_ok = os.path.exists("data/outputs/daily_report.json")
if report_ok:
    with open("data/outputs/daily_report.json") as f:
        data = json.load(f)
    monitor = data.get("monitor", {})
    bt = data.get("backtest", {})

    st.divider()
    st.subheader("📈 策略状态")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("状态", monitor.get("status", "?"))
    c2.metric("健康评分", f"{monitor.get('health_score', 0)}/100")
    c3.metric("趋势", monitor.get("trend", "?"))
    c4.metric("建议", monitor.get("note", "").split(":")[0] if monitor.get("note") else "?")

    if bt:
        c1, c2, c3, c4 = st.columns(4)
        metrics = bt.get("metrics", {})
        c1.metric("回测收益", f"{metrics.get('total_return', 0):+.1f}%")
        c2.metric("最大回撤", f"{metrics.get('max_drawdown', 0):.1f}%")
        c3.metric("胜率", f"{metrics.get('win_rate', 0):.0%}")
        c4.metric("夏普", metrics.get("sharpe", 0))

    # 持仓
    signal = data.get("signal", {})
    portfolio = signal.get("portfolio", []) if isinstance(signal, dict) else []
    if portfolio:
        st.subheader("📦 当前组合")
        df = pd.DataFrame(portfolio)
        st.dataframe(df, use_container_width=True)
else:
    st.info("📡 日报数据尚未生成。在 WorkBuddy 沙箱中运行 `python main.py` 或等待 GitHub Actions 执行。")

# ═══════════════════════════════════════════════
# 数据仓库样本
# ═══════════════════════════════════════════════
if csv_count > 0:
    with st.expander(f"📋 数据仓库样本 ({csv_count} 只)"):
        samples = sorted(os.listdir(csv_dir))[:30]
        st.write(", ".join(f.replace(".csv", "") for f in samples))
        st.caption("完整列表: data/raw/daily/")

# ═══════════════════════════════════════════════
# 使用说明书 (折叠)
# ═══════════════════════════════════════════════
with st.expander("📖 使用说明书"):
    if os.path.exists("docs/user_manual.md"):
        with open("docs/user_manual.md", encoding="utf-8") as f:
            st.markdown(f.read())

st.divider()
st.caption("v2.5 · GitHub Actions 每日自动更新 · "
           "[GitHub](https://github.com/typhoon322/RunDogRun)")
