# 🧭 RunDogRun V3 FINAL

> **统计收敛驱动交易系统 + 生命周期状态机 + 风险控制执行引擎**
>
> 不做预测 · 不做自动交易 · 不搞复杂模型

---

## 封版声明

RunDogRun V3 FINAL is a lifecycle-driven trading system.

**封版禁令 (永久):**
- ❌ 不引入机器学习
- ❌ 不做策略扩展
- ❌ 不增加因子
- ❌ 不做预测系统
- ❌ 不改结构，只调参数

**System evolves only via monthly parameter review in `config/params.yaml`.**

Every trade must pass through the Decision Engine. Every signal is snapshot-locked. Every state transition is logged. No exceptions.

---

## 四阶段状态机

```
COLLECT_ONLY → WARM_UP → ACTIVE → (MONITORING)
                                  ↑         ↓
                                  └── 降级 ──┘
```

| 阶段 | 行为 | 进入条件 |
|------|------|---------|
| COLLECT_ONLY | 只收数据 | days >= 10 → WARM_UP |
| WARM_UP | 评分+信号+IC (不交易) | score稳定 + 信号≥50 + IC≥0 → ACTIVE |
| ACTIVE | 完整交易闭环 | IC<0 或胜率突降 → WARM_UP |
| MONITORING | 每7天防失效检查 | 检测到问题 → WARM_UP |

## 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| 状态机 | `core/state_machine.py` | 生命周期管理，决定行为许可 |
| 决策引擎 | `execution/decision_engine.py` | 唯一决策入口，5种输出 |
| 稳定性 | `stats/stability.py` | Score 均值/标准差漂移检测 |
| 监控 | `report/monitor.py` | 防失效检查 (IC/胜率/漂移) |
| 飞书推送 | `core/feishu_sender.py` | 每日决策卡推送 |
| 配置 | `config/params.yaml` | 统一参数管理 |

## 决策矩阵 (5 actions)

| 条件 | 决策 |
|------|------|
| trend<50 or flow<45 or score<50 | EXIT 清仓退出 |
| 50≤score<60 | REDUCE 减仓50% |
| 60≤score<70 或 gates未通过 | NO_TRADE 观望不动 |
| 70≤score<80 + gates pass | BUY_SMALL 小仓试单 |
| score≥80 + gates pass | BUY_FULL 满仓买入 |

## 系统本质

这个系统不是用来让你更聪明的，而是用来保证你不会在市场里做蠢事。

```
数据 → 因子(trend/flow/value) → 评分 → 信号记录 → 前瞻收益验证
                                              ↓
                               🚨 交易生死门 (Hard Gate)
                                              ↓
                               💰 仓位控制 (30%/60%/100%)
                                              ↓
                               🧊 冷却系统 (亏损→强制休息)
                                              ↓
                               🔒 月度锁定 (30天才能改参数)
```

---

## 快速开始

```bash
pip install akshare pandas scipy streamlit
python pipeline/run_pipeline.py --top 5
```

GitHub Actions 每日自动执行 (北京时间 17:00)，结果自动推送到仓库。

---

## 核心功能

### 数据层
- **415 只股票 × 180+ 交易日** CSV 日线数据
- DataRegistry 统一调度，中英文表头兼容
- 增量同步，API 调用严格限频

### 因子层
- **trend** (趋势)：动量 + 板块强度
- **flow** (流动性)：成交量活跃度
- **value** (估值)：低价偏好
- **system_score**：三因子加权综合评分

### 执行规则层 (Hard Gate)
```
✅ 允许买入: trend ≥ 65 AND score ≥ 70 AND flow ≥ 55
🚫 禁止交易: 趋势崩坏 / 系统过热假强 / 流动性枯竭 / 冷却中
```

### 仓位控制
| Score | 仓位 |
|-------|------|
| < 70 | 不建仓 |
| 70–75 | 30% |
| 75–80 | 60% |
| 80+ | 100% (上限70%) |

- 风险压缩: trend<60 或 flow<55 → 最高30%
- 单票上限 10%，总仓上限 70%

### 冷却系统
- 1 次亏损 → 强制休息 3 天
- 连续 3 次亏损 → 强制休息 5 天

### 验证层
- 5 日前瞻收益回填
- IC 分析 (Score 预测力)
- 分桶统计 (0-50/50-65/65-75/75+)

### 月度锁定
- 参数每 30 天才能修改一次
- 必须基于数据支撑才能调整
- 所有变更记录版本日志

---

## 每日产出

| 文件 | 内容 |
|------|------|
| `output/daily_report.md` | Markdown 完整日报 |
| `output/daily_report_wechat.txt` | 微信版 (可复制) |
| `output/ic_report.json` | IC 分析报告 |
| `output/bucket_report.json` | 分桶统计 |
| `logs/signals.jsonl` | 信号历史 (每笔可追溯) |

---

## 项目结构

```
RunDogRun/
├── pipeline/run_pipeline.py   # 唯一入口 (20步闭环)
├── core/
│   ├── data_registry.py       # 数据统一调度 (OHLCV+前瞻收益)
│   ├── execution_rules.py     # 交易生死门+仓位+冷却+违例
│   ├── signal_logger.py       # 信号 JSONL 记录
│   ├── monthly_lock.py        # 月度参数锁定
│   └── data_days.py           # 交易日统计
├── analytics/
│   ├── forward_returns.py     # 前瞻收益引擎
│   ├── ic.py                  # IC 计算 (Pearson+Spearman)
│   └── bucket.py              # 分桶分析
├── trading/simulator.py       # 交易模拟器
├── optimizer/weight_optimizer.py  # 权重自动调优
├── report/
│   ├── generate_report.py     # 日报生成 (MD+微信)
│   └── system_health.py       # 系统健康评分
├── portfolio/
│   ├── sector_mapper.py       # 2000+ 股票→行业映射
│   └── analyze_portfolio.py   # 持仓偏离分析
├── app.py                     # Streamlit 仪表盘
├── data/
│   ├── raw/daily/             # 415 CSV 日线数据
│   ├── constitution.json      # 交易宪法 (所有参数)
│   ├── weights.json           # 因子权重
│   └── holdings.json          # 用户真实持仓
├── CONSTITUTION.md            # 封版宪法
└── .github/workflows/pipeline.yml  # GitHub Actions
```

---

## Streamlit 仪表盘

访问 `rundogrun.streamlit.app` 查看：

- 🧠 系统健康 + 交易日统计
- 🎯 今日决策 (BUY/OBSERVE/CLEAR/NO_TRADE)
- 💰 目标仓位 + 🧊 冷却状态 + 🔒 参数锁定
- 📊 IC 分析 + 分桶收益 + 模拟 PnL
- 📝 完整 Markdown 日报
- 📱 微信版日报 (可复制)
- ⬇️ 下载按钮

---

## 封版禁令

- ❌ 不得新增因子
- ❌ 不得引入机器学习
- ❌ 不得做预测系统
- ❌ 不得盘中改规则
- ❌ 不得临时调参

---

## 设计原则

1. **数据优先** — 数据不准，宁可不产出
2. **简单优先** — 可解释、可重复、可调试
3. **稳定性优先** — 稳定运行 > 数据完整 > 功能丰富
4. **不预测，只过滤** — 判断"该不该参与"，而非"会不会涨"

---

*V3.0-FINAL · 2026-06-30 封版 · [CONSTITUTION.md](CONSTITUTION.md)*
