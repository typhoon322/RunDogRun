"""
app.py — v2.5 策略监控仪表盘
================================
Streamlit UI → GitHub Actions 自动更新 → 手机可访问

部署: https://share.streamlit.io 选择此 repo, main branch, app.py
"""
import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="v2.5 Monitor", page_icon="📊", layout="wide")

st.title("📊 v2.5 策略监控仪表盘")
st.caption(f"自动更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ── 文件校验 + Pipeline 状态 ──
REPORT_PATH = "data/outputs/daily_report.json"
PIPELINE_PATH = "data/outputs/pipeline_log.json"

col1, col2 = st.columns(2)
col1.write(f"📄 report.json: {'✅' if os.path.exists(REPORT_PATH) else '❌ 缺失'}")
col2.write(f"📄 pipeline_log: {'✅' if os.path.exists(PIPELINE_PATH) else '❌ 缺失'}")

if os.path.exists(PIPELINE_PATH):
    with open(PIPELINE_PATH, "r") as f:
        pipeline = json.load(f)
    steps = pipeline.get("steps", [])
    with st.expander("🔧 Pipeline 执行详情"):
        pcols = st.columns(4)
        pcols[0].metric("总步骤", pipeline.get("total", 0))
        pcols[1].metric("✅ OK", pipeline.get("ok_count", 0))
        pcols[2].metric("❌ Fail", pipeline.get("fail_count", 0))
        for s in steps[-10:]:
            icon = {"ok": "✅", "fail": "❌", "skip": "⏭"}.get(s["status"], "❓")
            st.caption(f"{icon} `{s['step']}` {s.get('detail','')} ({s.get('time','')})")

if not os.path.exists(REPORT_PATH):
    st.error("❌ report.json 不存在 — 请检查 GitHub Actions 是否成功执行")
    st.stop()

# ── 加载报告数据 ──

with open(REPORT_PATH, "r") as f:
    data = json.load(f)

monitor = data.get("monitor", {})
bt = data.get("backtest", {})
signal = data.get("signal", {})
portfolio = (signal.get("portfolio", []) if isinstance(signal, dict) else [])

# ── 状态卡片 ──
status = monitor.get("status", "unknown")
health = monitor.get("health_score", 0)
rating = monitor.get("rating", "?")

color = {"TRADE": "green", "CAUTION": "orange", "STOP": "red"}.get(status, "gray")

col1, col2, col3, col4 = st.columns(4)
col1.metric("状态", status)
col2.metric("健康评分", f"{health}/100", delta=monitor.get("trend", ""))
col3.metric("评级", rating)
col4.metric("最近收益", bt.get("total_return_pct", "N/A"))

# ── 图表区 ──
st.subheader("📈 绩效指标")
cols = st.columns(6)
metrics_map = [
    ("胜率", "win_rate", "win_rate"),
    ("最大回撤", "max_drawdown", "max_drawdown_pct"),
    ("波动率", "volatility", "volatility"),
    ("夏普", "sharpe", "sharpe"),
]
bt_metrics = bt.get("metrics", {})
for i, (label, key, fallback) in enumerate(metrics_map[:4]):
    val = bt_metrics.get(key, bt_metrics.get(fallback, "—"))
    cols[i].metric(label, val)

# ── 监控详情 ──
st.subheader("🧠 监控详情")
col_a, col_b = st.columns(2)

with col_a:
    st.json(monitor)
with col_b:
    if bt_metrics:
        st.json({k: v for k, v in bt_metrics.items()
                 if k in ("total_return", "win_rate", "sharpe")})

# ── 持仓 ──
if portfolio:
    st.subheader("📦 当前组合")
    df = pd.DataFrame(portfolio)
    if not df.empty:
        st.dataframe(df, use_container_width=True,
                     column_config={"weight": st.column_config.NumberColumn(format="%.1f%%")})

# ── 系统使用说明书 ──
st.divider()
st.subheader("📖 系统使用说明书")

import os as _os
if _os.path.exists("docs/design.md"):
    with open("docs/design.md", "r", encoding="utf-8") as _f:
        st.markdown(_f.read())
else:
    st.info("说明书文件加载中...")

# ── 更新信息 ──
st.divider()
st.caption(f"数据: {data.get('date', '?')} · 系统: v2.5.2 · "
           f"[GitHub](https://github.com/typhoon322/RunDogRun)")
