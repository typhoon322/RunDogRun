# 📊 量化中线数据采集系统 v1 (数据与信号分离版)

> **稳定、低频、可靠地采集 A 股市场关键数据，并结构化存储**

🔗 不做交易 · 不做预测 · 不做自动下单

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行采集 (采集今日数据)
python main.py

# 3. 查看输出
cat data/$(date +%Y-%m-%d).json | python -m json.tool | head -50
```

---

## 什么是"量化中线数据采集系统"？

v1专注**一件事：每天收盘后自动采集关键市场数据**，结构化存储为标准化 JSON。

- ✅ **大盘指数行情** (上证、沪深300、创业板等8个指数)
- ✅ **行业板块排行** (全市场~100个东财行业板块，含涨跌家数+领涨股)
- ✅ **个股涨跌量能** (沪深300+中证500精选约150只代表性个股)
- ✅ **情绪指标** (涨停/跌停统计、风险评级、热门题材)
- ✅ **异常事件检测** (极端放量、集中涨停/跌停)

---

## 项目结构

```
rundog-data/
├── .github/workflows/
│   └── collect.yml          # GitHub Actions 每日自动采集+分析+交易
├── data/                     # 每日 JSON 输出
│   ├── YYYY-MM-DD.json       # v1 原始数据
│   ├── YYYY-MM-DD_watchlist.json  # v1.2 候选池
│   ├── YYYY-MM-DD_trade.json # v1.4 交易建议
│   ├── YYYY-MM-DD_cycle.json # v2 周期分析
│   ├── YYYY-MM-DD_execute.json # v4 终极执行
│   └── positions.json        # 持仓状态持久化
├── src/
│   ├── market.py            # 大盘指数 (腾讯财经)
│   ├── sector.py            # 行业板块 (东财 push2)
│   ├── stock.py             # 个股数据 (腾讯财经)
│   ├── sentiment.py         # 情绪指标 (同花顺+自算)
│   ├── sector_scorer.py     # Layer 1: 板块5维评分 (v1.1)
│   ├── stock_scorer.py      # Layer 2: 个股5维评分 (v1.2)
│   ├── analyzer.py          # 编排器: 历史读取+双层评分+候选池
│   ├── signals.py           # v1.3: 6种买卖信号检测
│   ├── position.py          # v1.4: 仓位分配 + 风控
│   ├── trade_engine.py      # 编排器: 状态机 + 执行建议
│   ├── cycle_engine.py       # v2: 7阶段板块周期模型
│   ├── trade_executor.py    # v3+v4: 龙头生命周期 + 资金风控
│   ├── regime_engine.py     # v5: 市场状态识别 + 策略切换
│   ├── validator.py         # 数据校验
│   └── utils.py             # HTTP重试/限流/工具
├── config.py                # 配置中心
├── main.py                  # 编排入口
└── requirements.txt
```

---

## 数据源架构

| 数据 | 来源 | 特点 |
|------|------|------|
| 大盘指数 | 腾讯财经 HTTP | 免费、不封IP、GBK编码 |
| 行业板块 | 东财 push2 | 零鉴权、~100行业板块 |
| 个股行情 | 腾讯财经 HTTP | 批量请求（每次50只）|
| 强势股/题材 | 同花顺热点 | 73ms、含题材归因 |

> **全部免费零key**，无需Tushare token，适合GitHub Actions环境。

---

## 输出样例

```json
{
  "date": "2026-06-27",
  "generated_at": "2026-06-27T18:00:00+08:00",
  "version": "1.0.0",
  "market": {
    "indices": [
      {
        "code": "000001",
        "name": "上证指数",
        "price": 3350.67,
        "change_pct": 0.83,
        "volume_ratio": 1.15,
        "pe_ttm": 14.2
      }
    ],
    "overall_return": 0.72,
    "overall_volume_ratio": 1.18,
    "market_status": "mild_bull"
  },
  "sectors": [
    {
      "name": "半导体",
      "code": "BK1036",
      "change_pct": 3.21,
      "strength_score": 8.4,
      "up_count": 85,
      "down_count": 22,
      "money_flow": "strong_inflow"
    }
  ],
  "stocks": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "return": 1.53,
      "volume_ratio": 1.83,
      "turnover_pct": 0.42,
      "trend_score": 6.8,
      "pe_ttm": 24.5,
      "mcap_yi": 21356.4
    }
  ],
  "sentiment": {
    "limit_up_count": 48,
    "limit_down_count": 3,
    "up_down_ratio": 16.0,
    "risk_level": "low",
    "top_themes": [
      {"name": "半导体", "count": 12},
      {"name": "AI算力", "count": 8}
    ]
  },
  "data_quality": "ok"
}
```

---

## 双层评分系统 (v1.1 + v1.2)

```bash
# 运行分析 (需先采集数据)
python main.py --analyze --date 2026-06-26
```

### Layer 1: 板块评分 (0-10分)

| 维度 | 说明 | 分数 |
|------|------|:--:|
| Trend | 5日+20日趋势 | 0-2 |
| Momentum | 3日 vs 10日加速度 | 0-2 |
| Money Flow | 资金持续性 | 0-2 |
| Breadth | 上涨家数占比 | 0-2 |
| Stability | 波动稳定性 | 0-2 |

分类: ≥8=主线板块, 6-7=强势轮动, 4-5=观察, <4=过滤

### Layer 2: 个股评分 (0-10分)

| 维度 | 说明 | 分数 |
|------|------|:--:|
| Trend | 趋势方向 | 0-2 |
| Relative Strength ⭐ | 是否跑赢板块 | 0-2 |
| Volume | 量能质量 | 0-2 |
| Structure | 价格结构 | 0-2 |
| Timing | 板块周期位置 | 0-2 |

### 候选池规则

1. 板块 Score ≥ 6 的板块
2. 这些板块中 Stock Score ≥ 7 的个股
3. 每板块保留 Top 3，全局不超过 30 只

---

## 交易信号与仓位风控 (v1.3 + v1.4)

```bash
python main.py --trade --date 2026-06-26
# → data/YYYY-MM-DD_trade.json
```

### 买入信号 (3种)

| 类型 | 条件 | 等级 |
|------|------|:--:|
| A: 突破 | 板块≥6 + 个股≥7 + 价>5日高 + 量≥1.5x | A+/A/B |
| B: 回踩 | 价>MA20 + 缩量 + 板块≥6 | B |
| C: 板块启动 | 板块刚晋级 + Breadth↑ + 龙头 | C |

### 卖出信号 (3种)

| 类型 | 条件 |
|------|------|
| D: 趋势破坏 | 价<MA20 + 放量下跌 + 板块<5 |
| E: 高潮衰竭 | 巨量(>3x)+滞涨+板块score↓ |
| F: 弱于板块 | 个股score<5 + RS<0 + 板块仍强 |

### 状态机

```
OBSERVE → ENTRY → HOLD → EXIT
```

### 仓位风控

| 规则 | 值 |
|------|-----|
| 单票上限 | 30% |
| A+/A/B/C 仓位 | 25-30% / 15-25% / 5-15% / 5% |
| 最大持仓 | 5 只 |
| 板块集中度 | ≤40% |
| 止损线 | -8% ~ -12% |

### 完整链路

```bash
python main.py --date DATE        # ① 数据采集
python main.py --analyze --date DATE  # ② 双层评分
python main.py --trade --date DATE    # ③ 交易信号
python main.py --cycle --date DATE    # ④ 板块周期
```

---

## 板块轮动周期模型 (v2)

```bash
python main.py --cycle --date 2026-06-26
# → data/YYYY-MM-DD_cycle.json
```

### 7阶段周期

```
沉寂 → 启动 → 确认 → 发酵 → 高潮 → 分化 → 退潮
```

| 阶段 | 含义 | v1 建议 |
|------|------|---------|
| 沉寂期 | 无资金关注 | 跳过 |
| 启动期 | 资金试探 | 观察龙头 |
| 确认期 | 主线确认 | 可加仓 |
| 发酵期 ⭐ | 最赚钱阶段 | 全力做多 |
| 高潮期 | 风险上升 | 谨慎 |
| 分化期 | 资金撤退 | 只减仓 |
| 退潮期 | 完全退出 | 禁止交易 |

### 市场总周期

| 状态 | 条件 |
|------|------|
| Risk-On | 多板块处于 Expansion/Confirm |
| Neutral | 混合状态 |
| Risk-Off | 多板块处于 Decline/Divergence |

### 核心原则

> 赚钱不来自选股，而来自"在正确周期做正确板块"

---

## 龙头生命周期 + 资金风控 (v3 + v4)

```bash
python main.py --execute --date 2026-06-26
# → data/YYYY-MM-DD_execute.json
```

### v3: 龙头生命周期 (7阶段)

启动 → 试盘 → 主升 🔥 → 加速 → 高潮 → 震荡 → 结束

| 阶段 | 动作 | 仓位 |
|------|------|:--:|
| 启动期 | 小仓试错 | 10-20% |
| 试盘期 | 逐步加仓 | 20-40% |
| 主升期 | 核心持仓 | 40-80% |
| 加速期 | 持有不加 | 20-50% |
| 高潮期 | 减仓 | 5-15% |
| 震荡期 | 清仓 | 0% |
| 结束期 | 空仓 | 0% |

### v4: 资金管理 + 回撤控制

| 市场 | 总仓位上限 |
|------|:--:|
| Risk-On | 70-90% |
| Neutral | 40-70% |
| Risk-Off | 0-40% |

| 回撤 | 动作 |
|------|------|
| -5% | 降仓20% |
| -10% | 降仓50% |
| -15% | 空仓观察 |

> v3 负责赚钱(吃主升浪), v4 负责不死(控制回撤)

---

## 市场状态识别 (v5)

```bash
python main.py --regime --date 2026-06-26
# → data/YYYY-MM-DD_regime.json
```

### 4大市场状态

| 状态 | 评分 | 策略模式 | 行为 |
|------|:--:|------|------|
| 趋势市 | 8-10 | aggressive | 满仓进攻 |
| 震荡市 | 6-7 | selective | 只做回踩 |
| 退潮市 | 4-5 | defensive | 降仓防守 |
| 恐慌市 | 0-3 | liquidation | 空仓 |

### v5 总控

> 先判断市场允许不允许赚钱，再决定用哪套交易系统

---

## 回测与强化学习 (v7 + v8)

```bash
python main.py --backtest   # v7 回测+优化
python main.py --train      # v8 RL Agent训练
```

### v7: 回测引擎

| 指标 | 说明 |
|------|------|
| 总收益/年化 | 策略盈利能力 |
| 最大回撤 | 风险暴露 |
| 胜率/盈亏比 | 交易质量 |
| 夏普比率 | 风险调整收益 |
| 策略评分 | 0-100综合评分 |

优化: Grid Search + Walk-Forward 滚动验证

### v8: Q-Learning 交易Agent

```
状态 → 动作 → 奖励 → 学习
```

状态空间: strong_bull / mild_bull / neutral / mild_bear / strong_bear
动作: BUY / HOLD / SELL / INCREASE / DECREASE / NO_ACTION

> v7负责证明系统有效，v8让系统自己变强

---

## GitHub Actions 配置

1. Fork 或创建仓库
2. 推送代码到 `main` 分支
3. GitHub Actions 自动按工作日定时执行
4. 或手动触发: Actions → "Quant Pipeline" → Run workflow

配置项 (可选):
- 修改 `config.py` 中的股票池、指数列表、评分参数
- 修改 `.github/workflows/collect.yml` 中的 cron 时间

---

## 后续扩展路线

- **v2**: 板块轮动模型 + 趋势评分模型
- **v3**: 信号系统 (买卖点检测)
- **v4**: 接入现有系统做联动分析

---

## 设计原则

1. **不追求实时** — 中线策略不需要秒级数据
2. **不追求复杂模型** — 先稳定比聪明重要
3. **数据优先级高于策略** — 没有干净数据，一切模型都是废的
4. **模块间容错降级** — 一个模块失败不影响其他
5. **宁慢不乱** — API调用严格控制频率
