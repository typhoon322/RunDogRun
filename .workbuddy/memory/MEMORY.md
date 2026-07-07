# RunDogRun — V3 FINAL 项目记忆

## 项目定位
A股量化中线交易系统 V3 FINAL。
- 不做预测、不做自动交易、不引入机器学习
- 统计收敛驱动交易系统 + 生命周期状态机 + 风险控制执行引擎
- 封版：只调参数不改架构，参数统一在 config/params.yaml 中管理
- 月度复盘窗口每30天可调参

## 核心架构 (V3 FINAL)
- **状态机**: `core/state_machine.py` — COLLECT_ONLY → WARM_UP → ACTIVE → 降级回滚
- **决策引擎**: `execution/decision_engine.py` — 5种输出 (EXIT/REDUCE/NO_TRADE/BUY_SMALL/BUY_FULL)
- **稳定性**: `stats/stability.py` — Score 均值/标准差漂移检测
- **监控**: `report/monitor.py` — 每7天防失效检查 (IC崩坏/胜率突降/Score漂移)
- **配置**: `config/params.yaml` — 统一参数文件
- **流水线**: `pipeline/run_pipeline.py` — 状态机驱动，行为由当前 STATE 决定

## 关键参数
- trend_min=65, flow_min=55, score_buy=70, score_strong=80
- score_caution=60, score_exit=50
- 仓位上限70%, 单票风险上限10%
- 冷却: 单亏3天, 三连亏5天

## 部署
- GitHub Actions 每日 15:15 北京时间触发
- Streamlit Cloud: rundogrun.streamlit.app
- 飞书通知: 每日决策卡推送
- GitHub: typhoon322/RunDogRun

## 技术栈
- Python 3.10 (GH Actions) / 3.13 (本地)
- AKShare + EastMoney + Sina + Tencent 数据源, 线程安全单例
- 4线程并发同步 + 熔断器模式
- 飞书 Webhook (base64 混淆)
