"""
app.py — v2.8 收官展示层
================================
Pipeline → output/ → Streamlit 只读
布局: 系统健康 → Markdown日报 → 微信版 → 下载 → 折叠详情
"""
import json
import os
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

# 北京时间
CN_TZ = timezone(timedelta(hours=8))
def now_cn():
    return datetime.now(CN_TZ)

st.set_page_config(page_title="RunDogRun v2.8", page_icon="📊", layout="wide")

# ═══════════════════════ 辅助 ═══════════════════════
def _read(filename: str):
    for d in ["output", "data/outputs"]:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None

def _read_json(filename: str) -> dict | None:
    p = _read(filename)
    if p:
        with open(p) as f:
            return json.load(f)
    return None

# ═══════════════════════ 标题 ═══════════════════════
now = now_cn()
st.title("📊 RunDogRun 每日策略系统")

# 从 pipeline_log 取最后一次执行时间
pipeline_log_raw = _read_json("pipeline_log.json")
if pipeline_log_raw:
    last_run = pipeline_log_raw.get("started", "")
    try:
        ts = datetime.fromisoformat(last_run)
        st.caption(f"数据更新: {ts.strftime('%Y-%m-%d %H:%M')} · 页面刷新: {now.strftime('%H:%M')}")
    except Exception:
        st.caption(f"页面刷新: {now.strftime('%Y-%m-%d %H:%M')}")
else:
    st.caption(f"页面刷新: {now.strftime('%Y-%m-%d %H:%M')}")

today_str = now.strftime("%Y-%m-%d")

# ═══════════════════════ 数据资产栏 ═══════════════════════
collection_days = _read_json("collection_days.json")
csv_dir = "data/raw/daily"
csv_count = len(os.listdir(csv_dir)) if os.path.exists(csv_dir) else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 数据仓库", f"{csv_count} 只", delta="股票覆盖")
if collection_days:
    c2.metric("📅 交易日", f"{collection_days['total_trading_days']} 天",
             delta=f"{collection_days['date_range']}" if collection_days.get('date_range') else None)
    c3.metric("📊 平均天数", f"{collection_days.get('per_stock_stats', {}).get('avg_days', 0)} 天/只")
    c4.metric("📋 Registry", "✅ 在线" if os.path.exists("data/registry.json") else "⚠ 待同步")
else:
    c2.metric("📅 交易日", "--", delta="等待首次采集")
    c3.metric("📊 平均天数", "--")
    c4.metric("📋 Registry", "⚠")

# ═══════════════════════ ① 系统健康 (顶栏) ═══════════════════════
sys_health = _read_json("system_health.json")
if sys_health:
    sh_score = sys_health.get("score", 0)
    sh_level = sys_health.get("level", "?")
    sh_date = sys_health.get("date", "")
    checks = sys_health.get("checks", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🧠 系统健康", f"{sh_score}/100", delta=f"{sh_level} {sh_date}")
    labels = {"data": "数据完整", "pipeline": "Pipeline", "backtest": "回测", "stability": "收益稳定"}
    for name, col in zip(["data", "pipeline", "backtest", "stability"], [c2, c3, c4, c1]):
        c = checks.get(name, {})
        icon = "✅" if c.get("ok") else "❌"
        col.caption(f"{icon} {labels.get(name, name)}: {c.get('detail', '?')[:30]}")
    st.caption(f"👉 {sys_health.get('verdict', '')}")

st.divider()

# ═══════════════════════ ② Markdown 日报 (核心展示) ═══════════════════════
md_path = _read("daily_report.md")
if md_path:
    with open(md_path, encoding="utf-8") as f:
        report_md = f.read()
    st.markdown(report_md, unsafe_allow_html=False)
else:
    st.warning("📡 日报尚未生成。等待 GitHub Actions 执行或本地运行 Pipeline。")

st.divider()

# ═══════════════════════ ③ 微信版 + 下载 ═══════════════════════
wx_path = _read("daily_report_wechat.txt")
col_wx, col_dl = st.columns([3, 1])

with col_wx:
    st.subheader("📱 微信版日报")
    if wx_path:
        with open(wx_path, encoding="utf-8") as f:
            wx_text = f.read()
        st.text_area("全选复制 → 粘贴到微信", wx_text, height=180,
                     label_visibility="collapsed")
    else:
        st.info("暂无微信版报告")

with col_dl:
    st.subheader("⬇️ 下载")
    if md_path:
        st.download_button(
            "📥 下载日报 .md",
            data=report_md,
            file_name=f"RunDogRun_{today_str}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    if wx_path:
        st.download_button(
            "📥 下载微信版 .txt",
            data=wx_text,
            file_name=f"RunDogRun_{today_str}_wx.txt",
            mime="text/plain",
            use_container_width=True,
        )

st.divider()

# ═══════════════════════ ④ 折叠详情 ═══════════════════════

# 持仓偏离分析
holdings_path = "data/holdings.json"
uni_path = "data/universe_cache.json"
if os.path.exists(holdings_path) and os.path.exists(uni_path):
    with st.expander("🧠 持仓偏离分析"):
        try:
            with open(holdings_path) as f:
                my_holdings = json.load(f)
            with open(uni_path) as f:
                uni_data = json.load(f)
            universe_codes = uni_data if isinstance(uni_data, list) else uni_data.get("codes", [])

            from portfolio.analyze_portfolio import build_portfolio_report
            pa = build_portfolio_report(my_holdings, universe_codes[:150])
            dev = pa.get("deviation", {})
            pscore = pa.get("deviation_score", {})

            c1, c2, c3 = st.columns(3)
            c1.metric("偏离评分", f"{pscore.get('score', 0)}/100", delta=pscore.get("level", ""))
            c2.metric("持仓", pa.get("holdings_count", 0))
            c3.metric("Universe", pa.get("universe_size", 0))

            dev_clean = {k: v for k, v in dev.items() if k != "未知"}
            top_dev = dict(sorted(dev_clean.items(), key=lambda x: abs(x[1]), reverse=True)[:8])
            if top_dev:
                st.caption("行业偏离 (正值=超配)")
                st.bar_chart(top_dev, use_container_width=True)

            parsed = pa.get("holdings", [])
            if parsed:
                df = pd.DataFrame(parsed)
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"⚠️ {e}")

# Pipeline 执行链
pipeline_log = _read_json("pipeline_log.json")
if pipeline_log:
    with st.expander("🔧 Pipeline 执行链"):
        c = st.columns(4)
        c[0].metric("📋 步骤", pipeline_log.get("total", 0))
        c[1].metric("✅ OK", pipeline_log.get("ok_count", 0))
        c[2].metric("❌ Fail", pipeline_log.get("fail_count", 0))
        c[3].metric("⏱ 耗时", f"{pipeline_log.get('elapsed_sec', 0):.0f}s")
        for s in pipeline_log.get("steps", []):
            icon = {"ok": "✅", "fail": "❌", "skip": "⏭"}.get(s["status"], "❓")
            st.caption(f"{icon} `{s['step']}`  {s.get('detail', '')}  _{s.get('time', '')}_")

# 回测曲线
equity_data = _read_json("equity_curve.json")
if equity_data:
    curve = equity_data.get("curve", [])
    if curve and len(curve) > 1:
        with st.expander("📉 回测曲线"):
            st.line_chart(curve)

# 数据仓库
csv_dir = "data/raw/daily"
csv_count = len(os.listdir(csv_dir)) if os.path.exists(csv_dir) else 0
if csv_count > 0:
    with st.expander(f"📋 数据仓库 ({csv_count} CSV)"):
        samples = sorted(os.listdir(csv_dir))[:50]
        st.write("  ".join(f.replace(".csv", "") for f in samples))
        st.caption(f"完整 {csv_count} 只 → data/raw/daily/")

# 使用说明书
with st.expander("📖 使用说明书"):
    if os.path.exists("docs/user_manual.md"):
        with open("docs/user_manual.md", encoding="utf-8") as f:
            st.markdown(f.read())

st.divider()
st.caption("v2.8 · Pipeline 闭环 + 自动日报 · "
           "[GitHub](https://github.com/typhoon322/RunDogRun)")
