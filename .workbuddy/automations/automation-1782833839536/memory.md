# Automation 1782833839536 — 每日收盘后数据收集 Pipeline

## 计划
- 频率：每个交易日 15:15（CST）后 ~5 分钟执行
- 流程：cd 到 /Users/yanx/Workbuddy/RunDogRun → python pipeline/run_pipeline.py → 解析 output/*.json → 用 lark-im 给 Yan.X 发执行摘要

## 执行摘要
- 2026-07-01 00:15 (Wed) 触发：v2.5-final 6 步轻量流程
  - 5/6 步通过，1 步失败（06_pipeline 因 05_fetch 返回 0 stocks）
  - 主体 3 分 36 秒完成；过程因 `| tail -150` 输出缓冲延迟退出
  - 飞书 bot 消息已发送至 Yan.X (open_id ou_81e27a3e4a66e4ac0fd619685803eed7)
  - 消息 ID: om_x100b6b0af52f3ca0c05230391157234
- 异常：akshare/东财数据源返回 0；本次未生成新 daily_report / portfolio_analysis
- 改进方向：避免 `| tail -150` 缓冲；考虑改用不依赖 akshare 的备用数据源；或在 fetch 失败时自动回退到本地缓存

