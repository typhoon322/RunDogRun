# 📖 RunDogRun V3 FINAL — 用户使用说明书

## 快速开始

```bash
pip install akshare pandas scipy streamlit
python pipeline/run_pipeline.py --top 5
```

## 你每天需要做什么

### 1️⃣ 打开 Streamlit

访问 `rundogrun.streamlit.app`，第一眼看到：

```
🧠 系统健康    🎯 今日决策    💰 目标仓位    🧊 冷却状态    🔒 参数锁定
100/100       🟢 BUY       30%            ✅ 正常         v3.0-FINAL
```

### 2️⃣ 看决策

| 看到 | 含义 | 你该做什么 |
|------|------|-----------|
| 🟢 BUY / STRONG_BUY | 允许交易 | 按目标仓位买入 |
| 🟡 OBSERVE | 只看不动 | 不买不卖 |
| 🔴 CLEAR / NO_TRADE | 禁止交易 | 清仓或空仓 |

### 3️⃣ 按仓位执行

| Score | 仓位 | 10万资金 |
|-------|------|----------|
| 70-75 | 30% | 3万 |
| 75-80 | 60% | 6万 |
| 80+ | 100% | 10万（实际上限7万） |

### 4️⃣ 不要做

- ❌ 盘中临时改主意
- ❌ 不满足 Hard Gate 强行买入
- ❌ 连续亏损后追回本

---

## 系统自动运行

系统每天 17:00 (北京时间) 通过 GitHub Actions 自动执行，不需要你手动触发。执行流程：

```
① 扫描数据仓库 (415 CSV)
② 生成 Universe (行业轮动)
③ 补齐缺失数据
④ 判断市场状态
⑤ 拉取全市场行情
⑥ 行业过滤 + 选股排名
⑦ 组合配置 (Top 5)
⑧ 信号记录 → logs/signals.jsonl
⑨ 回测验证
⑩ 监控评分 + 一致性检查
⑪ 执行规则判定 (Hard Gate)
⑫ 仓位计算
⑬ 日报输出 (JSON + Markdown + 微信版)
⑭ 系统健康评分
⑮ 交易日统计
⑯ 前瞻收益回填
⑰ IC 计算 + 分桶分析
```

---

## 输出文件一览

| 文件 | 内容 | 什么时候看 |
|------|------|-----------|
| `output/daily_report.md` | Markdown 完整日报 | 每天 |
| `output/daily_report_wechat.txt` | 微信版 (复制即用) | 每天 |
| `output/system_health.json` | 系统健康评分 | 出问题时 |
| `output/ic_report.json` | IC 分析 | 月度复盘 |
| `output/bucket_report.json` | 分桶统计 | 月度复盘 |
| `logs/signals.jsonl` | 信号历史 | 复盘回溯 |

---

## 微信日报使用

1. 打开 `output/daily_report_wechat.txt`
2. 全选 → 复制
3. 粘贴到微信任意对话

示例：
```
🟢 RunDogRun 日报 2026-07-01

📈 今日: +2.15%  📈 累计: +5.32%
🩺 策略: 75/100 · TRADE

📦 组合: 节能风电(23%)、有研硅(21%)、贤丰控股(19%)
📋 数据: 420/421 CSV OK

🧠 系统: 100/100 🟢 稳定
🎯 决策: 🟢 BUY

⚠️ 策略自动生成 · 仅供参考 · 17:05
```

---

## 月度复盘 (每30天一次)

1. 打开 Streamlit → 看 IC 分析 (Score 预测力)
2. 看分桶收益 (哪个分数段最赚钱)
3. 看模拟交易 PnL
4. 如有必要，在月度窗口调整参数 (`data/constitution.json`)
5. 所有修改记录在 `data/version_lock.json`

---

## 常见问题

**Q: 系统显示 NO_TRADE 怎么办？**
A: 说明当前不满足 Hard Gate (趋势/系统/流动性任一不足)。不要强行交易。

**Q: 冷却中是什么意思？**
A: 你最近亏过钱，系统强制让你休息。1次亏损3天，3连亏5天。等冷却结束再看。

**Q: 参数能改吗？**
A: 每30天可以改一次。打开 `data/constitution.json` 修改阈值，然后跑一次 Pipeline。

**Q: 数据不准怎么办？**
A: 系统用 AKShare 免费数据，偶尔断连正常。GitHub Actions 有容错机制，第二天会自动重试。

---

## 风险提示

- ⚠️ 本系统不做自动交易，仅输出分析信号
- ⚠️ 所有结果仅供参考，不构成投资建议
- ⚠️ 回测收益不代表未来表现
- ⚠️ 建议先用小资金验证 2-4 周

---

*V3.0-FINAL · 2026-06-30 封版*
