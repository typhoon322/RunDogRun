# 📖 v2.5 量化系统 — 用户使用说明书

## 快速开始

```bash
# 安装依赖
pip install akshare pandas streamlit

# 运行完整管道
python main.py --top 5
```

## 核心功能

本系统每天自动完成以下工作：

1. **扫描全市场** — 从 AkShare 获取 5000+ 只股票实时行情
2. **筛选强势行业** — 找出涨幅前 5 的行业板块
3. **精选低价龙头** — 动量强 + 价格低 + 成交量活跃
4. **组合分仓** — 自动分配权重，单票不超过 35%
5. **历史回测** — 用真实历史数据验证组合表现
6. **健康评分** — 输出 0-100 策略健康度
7. **日报输出** — JSON + Markdown 自动生成

## 命令一览

| 命令 | 作用 |
|------|------|
| `python main.py` | 完整管道 (默认 Top 5) |
| `python main.py --top 3` | 选 Top 3 组合 |
| `python main.py --top 10` | 选 Top 10 组合 |

## 输出文件

| 文件 | 内容 |
|------|------|
| `data/outputs/daily_report.json` | 主报告 (状态/指标/持仓) |
| `data/outputs/pipeline_log.json` | 管道执行日志 |
| `data/outputs/report.md` | Markdown 日报 |

## 仪表盘

部署到 Streamlit Cloud 后，手机打开 URL 即可看到：

- 📊 策略状态卡片 (TRADE/CAUTION/STOP)
- 📈 绩效指标 (胜率/回撤/波动/夏普)
- 📦 当前推荐组合持仓
- 🔧 Pipeline 每一步执行状态

## 自动化运行

GitHub Actions 每个工作日自动执行：

```
UTC 12:00 (北京时间 20:00)
  → 数据采集
  → 策略计算
  → 日报生成
  → 推送到 GitHub
  → Streamlit 仪表盘自动刷新
```

## 注意事项

- ⚠️ 本系统**不做自动交易**，仅输出分析信号
- ⚠️ 所有结果仅供参考，不构成投资建议
- ⚠️ 回测收益不代表未来表现
- ⚠️ 建议先用小资金验证 2-4 周

## 常见问题

**Q: 回测收益很高但策略评分低？**
A: 系统考虑了回撤和胜率，高收益但高回撤会被评为 CAUTION 或 STOP。

**Q: 提示 "NO_TRADE" 怎么办？**
A: 当前市场 MA5 < MA20，系统判定不适合交易，自动跳过。

**Q: Pipeline 某一步失败了？**
A: 查看 `data/outputs/pipeline_log.json`，里面有每一步的详细状态。

---

*系统版本: v2.5.2 · 自动更新*
