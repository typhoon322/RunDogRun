# 📖 v2.8 量化系统 — 用户使用说明书 (收官版)

## 快速开始

```bash
# 安装依赖
pip install akshare pandas streamlit

# 运行闭环 Pipeline (推荐)
python pipeline/run_pipeline.py --top 5
```

## 闭环架构

```
GitHub Actions (每日自动)
      ↓
Pipeline (统一入口)
  ├─ Registry 扫描 (413 CSV)
  ├─ Universe 生成 (行业轮动+稳定)
  ├─ 数据补齐 (自动同步缺失)
  ├─ 市场状态检查 (TRADE/CAUTION/STOP)
  ├─ 行业过滤 + 选股排名 + 组合配置
  ├─ 回测执行 (DataRegistry 统一入口)
  ├─ 监控评分 (0-100 健康度)
  └─ 日报输出 (JSON + Markdown + 微信版)
      ↓
Streamlit 仪表盘 (纯展示, 手机可看)
```

## 核心功能

每天自动完成：

1. **扫描全市场** — AkShare 获取 5000+ 只股票实时行情
2. **筛选强势行业** — 找出涨幅前 5 的行业板块
3. **精选低价龙头** — 动量强 + 价格<60 + 成交量活跃
4. **组合分仓** — 自动分配权重，单票≤35%
5. **历史回测** — DataRegistry 统一入口，真实历史数据
6. **健康评分** — 三维护康评分 (胜率/回撤/波动)
7. **自动日报** — Markdown + 微信友好版双输出

## 命令一览

| 命令 | 作用 |
|------|------|
| `python pipeline/run_pipeline.py` | 完整闭环 (默认 Top 5) |
| `python pipeline/run_pipeline.py --top 3` | Top 3 |
| `python pipeline/run_pipeline.py --top 10` | Top 10 |

## 输出文件

| 文件 | 内容 | 用途 |
|------|------|------|
| `output/daily_report.json` | 主报告 (JSON 结构化) | 数据对接 |
| `output/daily_report.md` | Markdown 完整日报 | Streamlit / GitHub 预览 |
| `output/daily_report_wechat.txt` | 微信友好版 | 直接复制发微信 |
| `output/pipeline_log.json` | Pipeline 执行日志 | 排错 |
| `output/equity_curve.json` | 回测资金曲线 | 图表展示 |

## 📱 微信日报使用方法

1. 打开 `output/daily_report_wechat.txt`
2. 全选复制
3. 粘贴到微信任意对话
4. 即可查看当日策略摘要

示例：

```
🟡 RunDogRun 日报 2026-06-28

📈 今日: +3.24%  📉 累计: -1.61%
🩺 健康: 60/100 · CAUTION

📦 组合: 节能风电(23%)、有研硅(21%)、贤丰控股(19%)
📋 数据: 413/414 CSV OK

💡 建议降仓, 观察回撤

⚠️ 策略自动生成 · 仅供参考
```

## 仪表盘

部署到 Streamlit Cloud (`rundogrun.streamlit.app`)：

- 📊 策略状态卡片 (TRADE/CAUTION/STOP)
- 📈 绩效指标 (胜率/回撤/波动)
- 📦 当前组合持仓
- 🔧 Pipeline 每步执行状态
- 📝 完整日报 (折叠展开)
- 💬 微信快速版 (复制即用)

## 自动化运行

GitHub Actions 每日自动：

```
UTC 14:00 (北京时间 22:00)
  → Pipeline 闭环执行
  → 日报自动生成
  → 推送到 GitHub
  → Streamlit 自动刷新
```

## 健康评分说明

| 评分 | 状态 | 含义 |
|------|------|------|
| 70-100 | 🟢 TRADE | 策略健康，可正常使用 |
| 50-69 | 🟡 CAUTION | 建议降仓观察 |
| 0-49 | 🔴 STOP | 建议暂停使用 |

评分维度：胜率(40分) + 回撤(30分) + 波动(30分)

## 注意事项

- ⚠️ 本系统**不做自动交易**，仅输出分析信号
- ⚠️ 所有结果仅供参考，不构成投资建议
- ⚠️ 回测收益不代表未来表现
- ⚠️ 建议先用小资金验证 2-4 周

## 常见问题

**Q: Pipeline 某一步失败了？**
A: 查看 `output/pipeline_log.json`，每一步有详细状态和时间。

**Q: 提示 "NO_TRADE"？**
A: 当前市场 MA5 < MA20，系统判定不适合交易，自动跳过。

**Q: 微信版在哪？**
A: `output/daily_report_wechat.txt`，每天 Pipeline 自动生成。

**Q: 如何回测更长时间？**
A: 数据仓库已有 413 只数年的 CSV 缓存。运行完整 Pipeline 即自动回测。

---

*系统版本: v2.6 · Pipeline 闭环 + 自动日报*
