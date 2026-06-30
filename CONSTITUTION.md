# RunDogRun V3 FINAL — 交易宪法

## 系统定位

> 这是一个「统计收敛驱动交易系统 + 生命周期状态机 + 风险控制执行引擎」
>
> **不是预测系统，不是研究平台，不是因子实验室。**

## 四阶段状态机

```
COLLECT_ONLY → WARM_UP → ACTIVE → (MONITORING)
                                  ↑         ↓
                                  └── 降级 ──┘
```

| 阶段 | 行为 | 进入条件 |
|------|------|---------|
| COLLECT_ONLY | 只收数据，不计算 | 初始状态 / --data-only |
| WARM_UP | 评分+信号+IC，不交易 | days >= 10 |
| ACTIVE | 完整交易闭环 | score稳定 + 信号≥50 + IC≥0 |
| MONITORING | ACTIVE 子状态，每7天检查 | 随 ACTIVE 自动激活 |

## 降级规则

- IC < 0 → ACTIVE → WARM_UP
- 胜率突降 > 15% → ACTIVE → WARM_UP
- Score 均值漂移 > 10% → WARNING

## 封版禁令（永久）

- ❌ 不得新增因子
- ❌ 不得引入机器学习模型
- ❌ 不得做预测系统
- ❌ 不得改为研究平台
- ❌ 不得做多策略组合
- ❌ 不得盘中改规则
- ❌ 不得临时调参
- ❌ 不得做复杂优化
- ❌ 不得改结构，只调参数

## 允许操作

- ✅ 每日跑 Pipeline 看结果
- ✅ 每 30 天在月度复盘窗口调整参数（需数据支撑）
- ✅ 记录交易盈亏触发冷却机制
- ✅ 参数调整仅在 config/params.yaml 中进行

## 核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| trend_min | 65 | 趋势最低线 |
| flow_min | 55 | 流动性最低线 |
| score_buy | 70 | 系统买入线 |
| score_strong | 80 | 可加仓线 |
| score_caution | 60 | 减仓线 |
| score_exit | 50 | 清仓线 |
| max_total_position | 70% | 总仓上限 |
| single_risk | 10% | 单票风险上限 |
| cooling_1_loss | 3天 | 单次亏损冷却 |
| cooling_3_loss | 5天 | 三连亏冷却 |
| review_interval | 30天 | 参数修改窗口 |
| monitor_interval | 7天 | 防失效检查周期 |

## 仓位映射

| Score | 仓位 |
|-------|------|
| < 70 | 不建仓 |
| 70–75 | 30% |
| 75–80 | 60% |
| 80+ | 100%（上限70%） |

## 决策矩阵 (V3 FINAL)

| 条件 | 决策 |
|------|------|
| trend < 50 or flow < 45 or score < 50 | EXIT 清仓退出 |
| 50 ≤ score < 60 | REDUCE 减仓50% |
| 60 ≤ score < 70 或 gates 未通过 | NO_TRADE 观望不动 |
| 70 ≤ score < 80 + gates pass | BUY_SMALL 小仓试单 |
| score ≥ 80 + gates pass | BUY_FULL 满仓买入 |

## 系统本质

> 这个系统不是用来让你更聪明，而是用来保证你不会在市场里做蠢事。

---

*V3.0-FINAL · 2026-06-30 封版*
