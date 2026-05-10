# Analysis Scripts

这个目录预留给“大样本分析但不直接生成网站”的入口脚本。

当前已实现：

- `run_stockfish_time_budget_sweep.py`
  - 复杂局面在不同 Stockfish 时间预算下的稳定性分析
  - pilot 配置：`configs/experiments/stockfish_time_budget_sweep_pilot_10.yaml`
- `run_rank_bucket_comparison.py`
  - `all eligible` vs `high complexity` 的实际走法排名对比
  - 当前 100 局配置：`configs/experiments/rank_bucket_comparison_100_games.yaml`

后续计划：

- `probe_realizability.py`
  - 可实现度特征提取与 Maia 对齐分析
  - 指标草案：`docs/experiments/realizability_metric_v0.md`

设计原则：

- 入口脚本只负责参数解析和产物落盘
- 核心逻辑放进 `src/analysis/`
- 输出优先写到 `outputs/analyses/<analysis_id>/`
