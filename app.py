"""
app.py — v2.5 Final 策略监控仪表盘 (纯展示层)
=======================================================
Pipeline → output/  → Streamlit 只读
零运行时依赖, 所有数据来自 Git 仓库文件
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
# 辅助: 双路径读取 (output/ 优先, data/outputs/ 兜底)
# ═══════════════════════════════════════════════
def read_json(filename: str) -> dict | None:
    for d in ["output", "data/outputs"]:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


# ═══════════════════════════════════════════════
# 顶栏: 系统状态速览
# ═══════════════════════════════════════════════
csv_dir = "data/raw/daily"
csv_count = len(os.listdir(csv_dir)) if os.path.exists(csv_dir) else 0
reg_exists = os.path.exists("data/registry.json")

daily_report = read_json("daily_report.json")
pipeline_log = read_json("pipeline_log.json")
equity_data = read_json("equity_curve.json")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📦 数据仓库", f"{csv_count} CSV", delta="Git 同步")
col2.metric("📋 Registry", "✅" if reg_exists else "⚠")
col3.metric("📊 日報", "✅" if daily_report else "❌")
col4.metric("⚙ Pipeline", "✅" if pipeline_log else "❌")

# ═══════════════════════════════════════════════
# Pipeline 执行详情
# ═══════════════════════════════════════════════
if pipeline_log:
    with st.expander("🔧 Pipeline 执行链"):
        c = st.columns(4)
        c[0].metric("步骤", pipeline_log.get("total", 0))
        c[1].metric("✅ OK", pipeline_log.get("ok_count", 0))
        c[2].metric("❌ Fail", pipeline_log.get("fail_count", 0))
        c[3].metric("⏱ 耗时", f"{pipeline_log.get('elapsed_sec', 0):.0f}s")
        for s in pipeline_log.get("steps", []):
            icon = {"ok": "✅", "fail": "❌", "skip": "⏭"}.get(s["status"], "❓")
            st.caption(f"{icon} `{s['step']}`  {s.get('detail','')}  _{s.get('time','')}_")

# ═══════════════════════════════════════════════
# 策略状态 (来自日報)
# ═══════════════════════════════════════════════
if daily_report:
    st.divider()
    st.subheader("📈 策略状态")

    monitor = daily_report.get("monitor", {})
    bt = daily_report.get("backtest", {})
    signal = daily_report.get("live_signal", {}) or daily_report.get("signal", {})
    consistency = daily_report.get("consistency", {})

    # 监控指标行
    c1, c2, c3, c4 = st.columns(4)
    status = monitor.get("status", "?")
    score = monitor.get("health_score", 0)
    emoji = {"TRADE": "🟢", "CAUTION": "🟡", "STOP": "🔴"}.get(status, "⚪")
    c1.metric(f"{emoji} 状态", status)
    c2.metric("健康评分", f"{score}/100")
    c3.metric("趋势", monitor.get("trend", "?"))
    c4.metric("建议", (monitor.get("note", "") or "").split(":")[-1].strip())

    # 回测指标行
    if bt:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总收益", f"{bt.get('total_return_pct', 0):+.1f}%")
        c2.metric("最大回撤", f"{bt.get('max_drawdown_pct', 0):.1f}%")
        c3.metric("胜率", f"{bt.get('win_rate', 0):.0%}")
        c4.metric("交易次数", bt.get("total_trades", 0))

    # 数据一致性
    if consistency:
        csv_ok = consistency.get("csv_ok", 0)
        csv_total = consistency.get("csv_total", 0)
        st.caption(f"📋 数据完整性: {csv_ok}/{csv_total} CSV OK  |  "
                   f"Registry: {consistency.get('registry_total', 0)} 只")

    # ═══════════════════════════════════════════
    # 回测曲线
    # ═══════════════════════════════════════════
    if equity_data:
        curve = equity_data.get("curve", [])
        if curve and len(curve) > 1:
            st.subheader("📉 回测曲线")
            st.line_chart(curve)

    # ═══════════════════════════════════════════
    # 当前组合持仓
    # ═══════════════════════════════════════════
    portfolio = signal.get("portfolio", []) if isinstance(signal, dict) else []
    if portfolio:
        st.subheader("📦 当前组合")
        df = pd.DataFrame(portfolio)
        cols = ["code", "name", "price", "score", "weight"]
        df = df[[c for c in cols if c in df.columns]]
        if "weight" in df.columns:
            df["weight"] = df["weight"].apply(lambda x: f"{x:.1%}")
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════
    # v2.6 日报 (Markdown 完整版)
    # ═══════════════════════════════════════════
    md_path = "output/daily_report.md"
    if not os.path.exists(md_path):
        md_path = "data/outputs/daily_report.md"
    if os.path.exists(md_path):
        with st.expander("📝 v2.6 每日策略报告 (完整版)"):
            with open(md_path, encoding="utf-8") as f:
                st.markdown(f.read())
    
    # v2.6 微信版
    wx_path = "output/daily_report_wechat.txt"
    if not os.path.exists(wx_path):
        wx_path = "data/outputs/daily_report_wechat.txt"
    if os.path.exists(wx_path):
        with st.expander("💬 微信快速版 (可复制)"):
            with open(wx_path, encoding="utf-8") as f:
                st.code(f.read(), language=None)

else:
    st.info("📡 日報尚未生成。Pipeline 将在 GitHub Actions 每日自动执行。\n\n"
            "本地运行: `python pipeline/run_pipeline.py --top 5`")

# ═══════════════════════════════════════════════
# 数据仓库概况
# ═══════════════════════════════════════════════
if csv_count > 0:
    with st.expander(f"📋 数据仓库 ({csv_count} CSV)"):
        samples = sorted(os.listdir(csv_dir))[:40]
        st.write("  ".join(f.replace(".csv", "") for f in samples))
        st.caption(f"完整 {csv_count} 只 → data/raw/daily/")

# ═══════════════════════════════════════════════
# 使用说明书
# ═══════════════════════════════════════════════
with st.expander("📖 使用说明书"):
    if os.path.exists("docs/user_manual.md"):
        with open("docs/user_manual.md", encoding="utf-8") as f:
            st.markdown(f.read())

st.divider()
st.caption("v2.6 · Pipeline 闭环 + 自动日报 · "
           "[GitHub](https://github.com/typhoon322/RunDogRun)")
