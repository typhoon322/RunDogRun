"""
report/generate_report.py — v2.6 每日策略报告生成器
=============================================================
输出两份报告:
  - output/daily_report.md         → Markdown 完整版 (Streamlit / GitHub)
  - output/daily_report_wechat.txt → 微信友好纯文本 (可直接复制)

数据来源: output/daily_report.json + output/equity_curve.json
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CN_TZ = timezone(timedelta(hours=8))

OUTPUT_DIR = "output"


def _read_json(filename: str) -> dict | None:
    for d in [OUTPUT_DIR, "data/outputs"]:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None


def _today_return(equity_curve: list[float]) -> float:
    """计算最近一日收益率"""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    return (equity_curve[-1] / equity_curve[-2] - 1) if equity_curve[-2] != 0 else 0.0


def _cumulative_return(equity_curve: list[float]) -> float:
    """累计收益率"""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    return equity_curve[-1] / equity_curve[0] - 1 if equity_curve[0] != 0 else 0.0


def _status_emoji(status: str) -> str:
    return {"TRADE": "🟢", "CAUTION": "🟡", "STOP": "🔴"}.get(status, "⚪")


def _health_label(score: int) -> str:
    if score >= 70:
        return "良好 ✅"
    elif score >= 50:
        return "一般 ⚠️"
    return "较差 🔴"


def _data_health_label(csv_ok: int, csv_total: int) -> str:
    if csv_total == 0:
        return "无数据 🔴"
    pct = csv_ok / csv_total
    if pct >= 0.98:
        return "正常 ✅"
    elif pct >= 0.90:
        return "一般 ⚠️"
    return "异常 🔴"


def generate_report():
    """生成 v2.6 日报 (Markdown + 微信版)"""
    now = datetime.now(CN_TZ)
    today_str = now.strftime("%Y-%m-%d %H:%M")
    today_date = now.strftime("%Y-%m-%d")

    # ── 读取数据 ──
    daily = _read_json("daily_report.json")
    equity = _read_json("equity_curve.json")
    sys_health = _read_json("system_health.json")

    curve = equity.get("curve", []) if equity else []
    bt_metrics = equity.get("metrics", {}) if equity else {}
    td_ret = _today_return(curve)
    cum_ret = _cumulative_return(curve)

    monitor = daily.get("monitor", {}) if daily else {}
    live_signal = daily.get("live_signal", {}) if daily else {}
    consistency = daily.get("consistency", {}) if daily else {}
    portfolio = live_signal.get("portfolio", [])
    signal_metrics = live_signal.get("metrics", {})
    backtest = daily.get("backtest", {}) if daily else {}

    status = monitor.get("status", "?")
    health = monitor.get("health_score", 0)
    rating = monitor.get("rating", "")
    note = monitor.get("note", "")
    trend = monitor.get("trend", "")

    csv_ok = consistency.get("csv_ok", 0)
    csv_total = consistency.get("csv_total", 0)
    registry_total = consistency.get("registry_total", 0)

    # 最新回撤
    max_dd = signal_metrics.get("max_drawdown", backtest.get("max_drawdown_pct", 0))

    # ── 读取数据仓库概况 ──
    data_dir = "data/raw/daily"
    csv_count = len(os.listdir(data_dir)) if os.path.exists(data_dir) else 0

    # ── 系统健康评分 ──
    from report.system_health import system_health_score
    sys_health = system_health_score()

    # ── 生成 Markdown ──
    md = _build_markdown(
        today_str, td_ret, cum_ret, status, health, rating, note, trend,
        portfolio, signal_metrics, backtest, max_dd,
        csv_count, csv_ok, csv_total, registry_total,
        sys_health,
    )

    # ── 生成微信版 ──
    wx = _build_wechat(
        today_date, td_ret, cum_ret, status, health, note,
        portfolio, csv_count, csv_ok, csv_total,
        sys_health,
    )

    # ── 写入文件 ──
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path("data/outputs").mkdir(parents=True, exist_ok=True)

    for d in [OUTPUT_DIR, "data/outputs"]:
        md_path = os.path.join(d, "daily_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

        wx_path = os.path.join(d, "daily_report_wechat.txt")
        with open(wx_path, "w", encoding="utf-8") as f:
            f.write(wx)

    print(f"📝 日报已生成 → {OUTPUT_DIR}/daily_report.md")
    print(f"💬 微信版已生成 → {OUTPUT_DIR}/daily_report_wechat.txt")


def _build_markdown(
    today_str, td_ret, cum_ret, status, health, rating, note, trend,
    portfolio, signal_metrics, backtest, max_dd,
    csv_count, csv_ok, csv_total, registry_total,
    sys_health=None,
) -> str:
    emoji = _status_emoji(status)
    health_label = _health_label(health)
    data_label = _data_health_label(csv_ok, csv_total)
    wr = backtest.get("win_rate", signal_metrics.get("win_rate", 0))

    md = f"""# 📊 v2.8 每日策略报告

> {today_str} · Pipeline 自动生成

---

## 📈 收益概况

| 指标 | 数值 |
|------|------|
| 今日收益 | {td_ret:+.2%} |
| 累计收益 | {cum_ret:+.2%} |
| 最大回撤 | {max_dd:.1f}% |
| 胜率 | {wr:.0%} |

---

## 🧠 策略状态

| 指标 | 状态 |
|------|------|
| 交易状态 | {emoji} **{status}** |
| 健康评分 | **{health}/100** {health_label} |
| 评级 | {rating} |
| 趋势 | {trend} |

> 💡 {note}

---

## 📦 当前组合

"""
    if portfolio:
        md += "| # | 代码 | 名称 | 价格 | 评分 | 权重 |\n"
        md += "|---|------|------|------|------|------|\n"
        for i, p in enumerate(portfolio):
            md += f"| {i+1} | {p['code']} | {p['name']} | ¥{p['price']} | {p['score']:.1f} | {p['weight']:.0%} |\n"
    else:
        md += "暂无持仓数据\n"

    md += f"""
---

## 📦 数据健康

| 指标 | 状态 |
|------|------|
| 数据仓库 | {csv_count} CSV |
| 完整性 | {csv_ok}/{csv_total} OK — {data_label} |
| Registry | {registry_total} 只 |

---

## 🧠 系统健康评分

"""
    if sys_health:
        checks = sys_health.get("checks", {})
        md += f"| 维度 | 评分 | 状态 |\n"
        md += f"|------|------|------|\n"
        labels = {"data": "数据完整", "pipeline": "Pipeline", "backtest": "回测产出", "stability": "收益稳定"}
        for name, c in checks.items():
            icon = "✅" if c["ok"] else "❌"
            md += f"| {labels.get(name, name)} | {c['score']}/25 | {icon} {c['detail']} |\n"
        md += f"\n| **综合** | **{sys_health['score']}/100** | **{sys_health['level']}** |\n"
        md += f"\n> 👉 {sys_health['verdict']}\n"

    md += f"""
---

## ⚠️ 风险提示

- 本报告由量化策略自动生成，**不构成投资建议**
- 策略基于历史数据回测，过去表现不代表未来收益
- 当前市场存在波动风险，请独立判断

---

*📡 v2.8 · [RunDogRun](https://github.com/typhoon322/RunDogRun)*
"""
    return md


def _build_wechat(
    today_date, td_ret, cum_ret, status, health, note,
    portfolio, csv_count, csv_ok, csv_total,
    sys_health=None,
) -> str:
    emoji = _status_emoji(status)
    td_symbol = "📈" if td_ret >= 0 else "📉"
    cum_symbol = "📈" if cum_ret >= 0 else "📉"

    # 组合摘要
    p_summary = ""
    if portfolio:
        top3 = portfolio[:3]
        p_summary = "、".join(f"{p['name']}({p['weight']:.0%})" for p in top3)

    wx = f"""{emoji} RunDogRun 日报 {today_date}

{td_symbol} 今日: {td_ret:+.2%}  {cum_symbol} 累计: {cum_ret:+.2%}
🩺 策略: {health}/100 · {status}

📦 组合: {p_summary if p_summary else '暂无'}
📋 数据: {csv_ok}/{csv_total} CSV OK
"""
    # 系统健康
    if sys_health:
        sh_score = sys_health.get("score", 0)
        sh_level = sys_health.get("level", "")
        wx += f"\n🧠 系统: {sh_score}/100 {sh_level}"

    # v3 FINAL 执行决策 (从 daily_report.json 读取)
    execution = daily.get("execution", {}) if daily else {}
    if execution:
        exec_emoji = execution.get("emoji", "")
        exec_decision = execution.get("decision", "")
        wx += f"\n🎯 决策: {exec_emoji} {exec_decision}"
    
    wx += f"""

💡 {note}

⚠️ 策略自动生成 · 仅供参考 · {datetime.now(CN_TZ).strftime('%H:%M')}
"""
    return wx


if __name__ == "__main__":
    generate_report()
