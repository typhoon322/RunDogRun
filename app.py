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

st.set_page_config(page_title="RunDogRun", page_icon="📊", layout="wide")

# 移动端适配: 标题字号缩小
st.markdown("""
<style>
@media (max-width: 768px) {
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 1.0rem !important; }
    .stCaption { font-size: 0.75rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════ 辅助 ═══════════════════════
def _read(filename: str):
    for d in ["output", "data/outputs", "data"]:
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

# ═══════════════════════ 执行决策卡片 ═══════════════════════
daily_report = _read_json("daily_report.json")
if daily_report:
    exec_data = daily_report.get("execution", {})
    if exec_data:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🎯 今日决策", f"{exec_data.get('emoji','')} {exec_data.get('decision','')}")
        factors = exec_data.get("factors", {})
        c2.metric("📈 趋势", f"{factors.get('trend',0):.0f}", delta="≥65可交易")
        c3.metric("💧 流动性", f"{factors.get('flow',0):.0f}", delta="≥55可交易")
        c4.metric("🎯 综合评分", f"{factors.get('score',0):.0f}", delta="≥70买入")
        details = exec_data.get("details", [])
        if details:
            for d in details:
                st.caption(d)
        pa = exec_data.get("position_action", {})
        if pa and pa.get("action") != "HOLD":
            st.warning(f"⚠️ 仓位建议: {pa.get('reason','')}")

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

# ═══════════════════════ V3 分析板块 ═══════════════════════
st.divider()
st.subheader("📊 V3 策略质量分析")

# IC 报告
ic_data = _read_json("ic_report.json")
if ic_data:
    with st.expander("📈 IC 分析 (Score 预测力)"):
        ic5 = ic_data.get("ic_5d", {})
        ric5 = ic_data.get("rank_ic_5d", {})
        decay = ic_data.get("ic_decay", {})
        rolling = ic_data.get("rolling_ic", [])

        c1, c2, c3 = st.columns(3)
        ic_v = ic5.get("ic")
        c1.metric("IC (5日)", f"{ic_v:+.4f}" if ic_v else "--",
                 delta="正向预测" if (ic_v and ic_v > 0) else "无效")
        ric_v = ric5.get("rank_ic")
        c2.metric("Rank IC", f"{ric_v:+.4f}" if ric_v else "--")
        c3.metric("信号总数", ic_data.get("n_signals", 0))

        if decay:
            st.caption(f"IC 衰减: " + " | ".join(f"{k}={v:+.4f}" if v else f"{k}=N/A" for k, v in decay.items()))
        if rolling:
            st.line_chart({r["date"]: r["ic"] for r in rolling}, use_container_width=True)

# 分桶报告
bucket_data = _read_json("bucket_report.json")
if bucket_data:
    buckets = bucket_data.get("buckets", [])
    if buckets:
        with st.expander("🔍 评分分桶收益 (Score越高收益越高?)"):
            import pandas as pd
            bdf = pd.DataFrame([b for b in buckets if b.get("count", 0) > 0])
            if not bdf.empty:
                c1, c2 = st.columns(2)
                with c1:
                    st.bar_chart(bdf.set_index("bucket")["avg_return"], use_container_width=True)
                with c2:
                    st.dataframe(bdf[["bucket", "count", "avg_return", "win_rate", "sharpe"]],
                                use_container_width=True, hide_index=True)

# 模拟交易
sim_data = _read_json("sim_pnl.json")
if sim_data:
    m = sim_data.get("metrics", {})
    if m:
        with st.expander("📉 模拟交易 (score≥60买入,持有5天)"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("总收益", f"{m.get('total_return', 0):+.2%}")
            c2.metric("胜率", f"{m.get('win_rate', 0):.0%}")
            c3.metric("夏普", m.get("sharpe", 0))
            c4.metric("交易次数", m.get("n_trades", 0))
            curve = sim_data.get("pnl_curve", [])
            if curve:
                st.line_chart(curve, use_container_width=True)

# 权重面板
weights_path = "data/weights.json"
if os.path.exists(weights_path):
    with st.expander("🔧 因子权重配置"):
        import json as _json
        with open(weights_path) as f:
            w = _json.load(f)
        for k, v in w.items():
            labels = {"momentum": "动量(涨跌幅)", "price_value": "低价偏好", "volume": "成交量", "sector": "板块加成"}
            st.caption(f"{labels.get(k, k)}: **{v:.1%}**")

# 使用说明书
with st.expander("📖 使用说明书"):
    if os.path.exists("docs/user_manual.md"):
        with open("docs/user_manual.md", encoding="utf-8") as f:
            st.markdown(f.read())

st.divider()
st.caption("v2.8 · Pipeline 闭环 + 自动日报 · "
           "[GitHub](https://github.com/typhoon322/RunDogRun)")
