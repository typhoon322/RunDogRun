"""
app.py — V3 FINAL 展示层
================================
Pipeline → output/ → Streamlit 只读
布局: 状态机 → 系统健康 → Markdown日报 → 微信版 → 下载 → 折叠详情
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

st.set_page_config(page_title="RunDogRun V3", page_icon="📊", layout="wide")

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
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None

# ═══════════════════════ 标题 ═══════════════════════
now = now_cn()
st.title("📊 RunDogRun V3 每日策略系统")

# 从 pipeline_log 取最后一次执行时间
pipeline_log_raw = _read_json("pipeline_log.json")
if pipeline_log_raw:
    last_run = pipeline_log_raw.get("started", "")
    try:
        ts = datetime.fromisoformat(last_run)
        st.caption(f"Pipeline 版本: {pipeline_log_raw.get('pipeline', 'v3.0')} · 数据更新: {ts.strftime('%Y-%m-%d %H:%M')} · 页面刷新: {now.strftime('%H:%M')}")
    except Exception:
        st.caption(f"页面刷新: {now.strftime('%Y-%m-%d %H:%M')}")
else:
    st.caption(f"页面刷新: {now.strftime('%Y-%m-%d %H:%M')}")

today_str = now.strftime("%Y-%m-%d")

# ═══════════════════════ 状态机检测 ═══════════════════════
daily_report = _read_json("daily_report.json")

# 从 state_machine 字段或 pipeline_status 字段推断当前状态
SM_EMOJI = {"COLLECT_ONLY": "❄️", "WARM_UP": "🔥", "ACTIVE": "🚀", "MONITORING": "🧠"}
SM_LABELS = {
    "COLLECT_ONLY": "冷启动: 仅数据收集",
    "WARM_UP": "统计预热: 评分+IC, 不交易",
    "ACTIVE": "实盘执行: 完整交易闭环",
    "MONITORING": "监控中: 防失效检查",
}

_state = "COLLECT_ONLY"  # 默认
if daily_report:
    sm = daily_report.get("state_machine", {})
    _state = sm.get("state", "")
    if not _state:
        # 向后兼容: 从 pipeline_status 推断
        status = daily_report.get("pipeline_status", "")
        if status in ("COLD_START", "DATA_ONLY", "COLLECT_ONLY"):
            _state = "COLLECT_ONLY"
        elif status in ("WARMUP_STAT", "WARM_UP"):
            _state = "WARM_UP"
        elif status in ("ACTIVE", "MONITORING"):
            _state = "ACTIVE"
        elif status == "SKIPPED":
            _state = "ACTIVE"  # 假设已进入ACTIVE但跳过
        else:
            _state = "WARM_UP"  # 未知默认WARM_UP
_is_warmup = _state in ("COLLECT_ONLY", "WARM_UP")
_emoji = SM_EMOJI.get(_state, "❓")
_label = SM_LABELS.get(_state, _state)

# 状态机卡片
with st.container():
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🔁 系统状态", f"{_emoji} {_state}")
    with c2:
        st.metric("📡 交易状态", "观望/不交易" if _is_warmup else "🚀 可交易")
    days_info = daily_report.get("data_days", {}) if daily_report else {}
    with c3:
        st.metric("📅 数据天数", f"{days_info.get('total_trading_days', 0)}天")
    with c4:
        min_d = days_info.get("per_stock_stats", {}).get("min_days", 0)
        st.metric("📊 最少覆盖", f"{min_d}天")

if _is_warmup:
    warmup = daily_report.get("warmup", {})
    data_days = daily_report.get("data_days", {})
    reg_stats = daily_report.get("registry_stats", {})
    min_d = warmup.get("min_days", 0)
    target_d = warmup.get("target_days", 30)
    remaining = warmup.get("remaining_days", 0)
    progress_pct = min(min_d / max(target_d, 1), 1.0)

    # 预热信息
    st.warning(f"{_emoji} {_label} — min_days={min_d}")
    st.progress(progress_pct, text=f"数据积累: {min_d} 天 · 目标进入 {warmup.get('next_phase', 'ACTIVE')}: 还需约 {remaining} 个交易日")

    # 数据覆盖率指标
    wc1, wc2, wc3, wc4, wc5 = st.columns(5)
    wc1.metric("📦 CSV 总量", f"{data_days.get('csv_count', reg_stats.get('total_csv', 0))}")
    wc2.metric("📅 交易日", f"{data_days.get('total_trading_days', 0)} 天")
    wc3.metric("📊 平均覆盖", f"{data_days.get('per_stock_stats', {}).get('avg_days', 0):.0f} 天/只")
    wc4.metric("📉 最少覆盖", f"{data_days.get('per_stock_stats', {}).get('min_days', 0)} 天",
              delta="⚠ 部分新股数据不足" if min_d < target_d else "✅ 达标")
    wc5.metric("🌐 Universe", f"{daily_report.get('universe_size', 0)} 只")

    st.caption(f"📅 数据范围: {data_days.get('date_range', '--')} · "
               f"最后更新: {data_days.get('last_date', '--')}")

    # ═══ Warm-up 统计看板 ═══
    if _state == "WARM_UP":
        wstats = daily_report.get("warmup_stats", {})
        if wstats:
            st.divider()
            st.subheader("📊 预热统计看板")

            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("📋 评分股票", f"{wstats.get('score_count', 0)} 只")
            sc2.metric("📝 累计信号", f"{wstats.get('signal_count', 0)} 条")
            ic_v = wstats.get("ic_5d")
            sc3.metric("📈 IC (5日)", f"{ic_v:+.4f}" if ic_v is not None else "积累中",
                       delta="🟢 有效" if (ic_v and ic_v > 0.03) else "⏳ 待积累")
            ric_v = wstats.get("rank_ic_5d")
            sc4.metric("📊 Rank IC", f"{ric_v:+.4f}" if ric_v is not None else "积累中")

            # Score 分布
            dist = wstats.get("score_distribution", [])
            if dist:
                with st.expander("📊 Score 分布"):
                    import pandas as _pd
                    ddf = _pd.DataFrame(dist)
                    if not ddf.empty:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.bar_chart(ddf.set_index("bucket")["count"], use_container_width=True)
                        with c2:
                            st.dataframe(ddf, use_container_width=True, hide_index=True)

            # 因子统计
            factor_stats = wstats.get("factor_stats", {})
            if factor_stats:
                with st.expander("🔧 因子统计 (trend / flow / value)"):
                    rows = []
                    for fname, fstats in factor_stats.items():
                        rows.append({
                            "因子": fname,
                            "均值": fstats.get("mean", 0),
                            "标准差": fstats.get("std", 0),
                            "最小值": fstats.get("min", 0),
                            "最大值": fstats.get("max", 0),
                        })
                    st.dataframe(rows, use_container_width=True, hide_index=True)

            # Top 10 评分股票
            top_stocks = wstats.get("top_stocks", [])
            if top_stocks:
                with st.expander("🏆 Top 10 评分股票 (仅供参考, 不构成交易建议)"):
                    st.dataframe(top_stocks, use_container_width=True, hide_index=True)

            # IC 衰减
            ic_decay = wstats.get("ic_decay", {})
            if ic_decay:
                with st.expander("📉 IC 衰减曲线"):
                    decay_items = [(k, v) for k, v in ic_decay.items() if v is not None]
                    if decay_items:
                        st.bar_chart({k: v for k, v in decay_items}, use_container_width=True)
                        st.caption("IC 衰减: 不同持有期限下 Score 的预测力变化")

            # 分桶
            buckets = wstats.get("buckets", [])
            if buckets:
                with st.expander("🔍 评分分桶收益 (积累中)"):
                    valid_buckets = [b for b in buckets if b.get("count", 0) > 0]
                    if valid_buckets:
                        st.dataframe(valid_buckets, use_container_width=True, hide_index=True)
                    else:
                        st.caption("⏳ 分桶数据积累中, 需更多信号")

    with st.expander("📖 预热说明"):
        st.markdown("""
**三阶段智能预热**

| 阶段 | 条件 | 做什么 | 不做什么 |
|------|------|--------|----------|
| ❄️ Phase 1 | min_days < 10 | 数据收集 | 评分、交易 |
| 🔥 Phase 2 | 10 ≤ min < 30 | 评分、信号记录、IC/分桶统计 | 交易决策、仓位 |
| 🚀 Phase 3 | min_days ≥ 30 | 完整闭环 | — |

**Phase 2 的价值**
- 每天计算 Score 并记录信号, 但不做交易决策
- 积累 IC (信息系数) 统计, 验证 Score 的预测力
- 分桶分析: 高分股是否真的收益更高?
- 等 min_days ≥ 30 后自动进入 Phase 3 完整交易

**你可以做什么？**
- Phase 1: 看数据覆盖率增长
- Phase 2: 看 Score 分布、IC 趋势、分桶验证
- Phase 3: 完整策略日报、执行决策、回测曲线
""")
    st.divider()

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
if sys_health and not _is_warmup:
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
if daily_report and not _is_warmup:
    exec_data = daily_report.get("execution", {})
    if exec_data:
        st.divider()
        # 决策颜色
        decision_colors = {
            "EXIT": "🔴", "REDUCE": "🟠", "NO_TRADE": "🟡",
            "BUY_SMALL": "🟢", "BUY_FULL": "🟢",
        }
        dec = exec_data.get("decision", "NO_TRADE")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🎯 今日决策", f"{decision_colors.get(dec, '❓')} {dec}")
        factors = exec_data.get("factors", {})
        c2.metric("📈 趋势", f"{factors.get('trend',0):.0f}", delta="≥65可交易")
        c3.metric("💧 流动性", f"{factors.get('flow',0):.0f}", delta="≥55可交易")
        c4.metric("🎯 综合评分", f"{factors.get('score',0):.0f}", delta="≥70买入")
        details = exec_data.get("details", [])
        if details:
            for d in details:
                st.caption(d)
        if exec_data.get("in_danger"):
            st.error(f"⚠️ 风险警告: 当前决策 {dec} — 建议关注风险")

    # V3 FINAL: 仓位 + 锁定
    pos_data = daily_report.get("position", {}) if daily_report else {}
    lock_data = daily_report.get("lock", {}) if daily_report else {}
    if pos_data or lock_data:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 目标仓位", f"{pos_data.get('target_pct',0):.0%}",
                 delta="压缩" if pos_data.get('compressed') else pos_data.get('reason','')[:15])
        cooling = pos_data.get("cooling", {})
        c2.metric("🧊 冷却状态", "🔒冷却中" if cooling.get("in_cooldown") else "✅ 正常",
                 delta=f"连亏{cooling.get('consecutive_losses',0)}次")
        c3.metric("🔒 参数锁定", lock_data.get("version", "v3"),
                 delta="✅可改" if lock_data.get("can_modify") else "🔒锁定")
        c4.metric("📅 下次可改", lock_data.get("next_allowed", "-"))

# ═══════════════════════ 状态机历史 ═══════════════════════
sm = daily_report.get("state_machine", {}) if daily_report else {}
hist = sm.get("history", [])
if hist:
    with st.expander(f"🔄 状态转换历史 ({len(hist)} 次)"):
        for h in hist:
            st.caption(f"{h.get('from','')} → {h.get('to','')} | {h.get('reason','')} | {h.get('timestamp','')[:16]}")

st.divider()

# ═══════════════════════ ② Markdown 日报 (核心展示) ═══════════════════════
md_path = _read("daily_report.md")
if _is_warmup:
    st.info(f"📡 {_emoji} {_label} — 策略日报将在进入 ACTIVE (信号≥50 + IC≥0 + score稳定) 后自动生成")
elif md_path:
    with open(md_path, encoding="utf-8") as f:
        report_md = f.read()
    st.markdown(report_md, unsafe_allow_html=False)
else:
    st.warning("📡 日报尚未生成。等待 GitHub Actions 执行或本地运行 Pipeline。")

st.divider()

# ═══════════════════════ ③ 微信版 + 下载 ═══════════════════════
if not _is_warmup:
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

# 持仓偏离分析 (预热期跳过)
holdings_path = "data/holdings.json"
uni_path = "data/universe_cache.json"
if not _is_warmup and os.path.exists(holdings_path) and os.path.exists(uni_path):
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
if not _is_warmup:
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
if not _is_warmup:
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
