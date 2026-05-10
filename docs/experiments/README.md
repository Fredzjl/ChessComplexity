# Follow-up Experiment Tracks

这份说明把下一阶段的 3 个实验先定成一个统一的研究骨架。先把口径、输入、产物和实现顺序写清楚，后面我们就可以一项一项落地，而不是每次重新定义问题。

## Shared assumptions

- 统一从现有结构化数据和运行产物出发
  - `outputs/runs/<run_id>/step_04_parse_filter/`
  - `outputs/runs/<run_id>/step_06_policy_expansion/`
  - `outputs/runs/<run_id>/step_07_complexity_scoring/`
- 默认还是只看中局筛选后的局面
- `complex position` 暂时仍然用当前定义
  - `3-ply`
  - `Maia probability >= 0.10`
  - `complexity_score >= 10`
- 后面如果复杂度定义更新，这 3 个实验都应该支持直接复跑

## Experiment 1: Stockfish Time-Budget Sweep

### Research question

对于我们已经筛出来的复杂局面，只看 `Stockfish`，在不同的思考时间下：

- 最佳步会不会明显变化
- 评分会不会剧烈漂移
- PV 会不会频繁改写
- 真人实际走法的引擎排名会不会随时间预算明显跳动

### Why this matters

如果一个局面在 `50ms`、`1s`、`60s` 下的引擎判断都不稳定，那它很可能不是“普通复杂”，而是“连引擎短时搜索也容易改口”的局面。这会给我们一个和 `Maia` 完全独立的复杂性视角。

### Recommended time budgets

先用一组跨度大、但总成本还可控的档位：

- `50 ms`
- `200 ms`
- `1000 ms`
- `5000 ms`
- `15000 ms`
- `60000 ms`

解释：

- `50/200 ms` 模拟很短的快速判断
- `1 s` 是一个比较实用的轻量基线
- `5/15 s` 可以看中等深度稳定性
- `60 s` 作为“晚间慢跑”的最深一档

### Minimum outputs

- 每个时间档的根节点分析结果
- 每个局面的时间预算稳定性摘要
- 不稳定局面的 shortlist
- 可接入网站的 JSON/CSV

### Suggested metrics

- `best_move_switch_count`
  - 不同时间档之间最佳步改了几次
- `best_score_range_cp`
  - 最佳步评分范围
- `actual_move_rank_range`
  - 真人实际走法的引擎排名波动
- `topk_overlap`
  - 相邻时间档 top-k 集合重叠程度
- `pv_prefix_stability`
  - PV 前 2 到 4 手是否稳定

### Proposed artifact layout

```text
outputs/analyses/<analysis_id>/
  stockfish_time_budget/
    root_analysis_by_budget.jsonl
    position_stability.csv
    unstable_positions.csv
    metadata/
      summary.json
      summary.md
```

## Experiment 2: Actual-Move Rank Comparison by Elo Bucket

### Research question

把局面分成：

- `all eligible positions`
- `complex positions only`

然后比较真人实际走法在 `Maia` 和 `Stockfish` 里的排名表现，看看复杂局面是不是确实让模型更难预测，尤其是 `Maia`。

### Population definition

- 只看当前轮到走棋的一方 Elo
- 只保留 `player_elo >= 1000`
- 每 `100` 分一个桶
  - `1000-1099`
  - `1100-1199`
  - ...

### Why use side-to-move Elo

这个实验关注的是“当前做决策的人类”，所以分桶应该基于当前走棋方的 Elo，而不是整盘棋平均 Elo。

### Main comparison slices

- `all eligible`
- `high complexity only`
- 可选扩展：`high complexity + conflict subsets`

### Suggested metrics

对每个 Elo bucket、每个 slice、每个模型都输出：

- `mean_actual_rank`
- `median_actual_rank`
- `hit_at_1`
- `hit_at_3`
- `hit_at_5`
- `coverage`
  - 尤其是 `Stockfish`，要明确记录真人步是否出现在分析候选中

### Important implementation note for Stockfish

这个实验里，`Stockfish` 的“排名”不能只靠浅层 `top-20`。更稳妥的做法是：

- 至少单独求出真人实际走法的分数
- 再把它和引擎候选列表一起排位
- 如果后面需要更严谨，可以做一次更完整的 legal-move ranking pass

### Minimum outputs

- bucket 级别的比较表
- “所有局面 vs 复杂局面”的并列表
- 适合画图的长表
- 一份简要结论报告

### Proposed artifact layout

```text
outputs/analyses/<analysis_id>/
  rank_bucket_comparison/
    bucket_summary.csv
    position_level_ranks.csv
    chart_ready_long.csv
    metadata/
      summary.json
      summary.md
```

## Experiment 3: Realizability / Convertibility Metric

### Research question

一个引擎说“有优势”的选择，到底是不是人类容易兑现的优势？

换句话说：

- 是不是只要走几个自然步，就能把优势拿到手
- 还是必须连续多步唯一/唯二、容错率极低，才兑现得出来

### Working assumption

这里我先采用一个明确口径：

- `需要连续多步唯一或极少数精确走法`
  - `realizability` 低
- `存在较宽的安全兑现路径`
  - `realizability` 高

如果你后面想换成反向记分，也可以，但我建议先把语义固定成这样。

### First-pass feature set

先不要一上来硬压成一个分数，先保留可解释特征：

- `initial_gain_cp`
  - 候选步相对基线能拿到多少优势
- `acceptable_width_d1`
  - 下一手有多少种走法还能保住大部分收益
- `acceptable_width_d3`
  - 往后 3 ply 里，安全分支有多宽
- `unique_burden_plies`
  - 连续多少 ply 处在“只有 1 到 2 步可接受”的状态
- `deviation_penalty_cp`
  - 第一次偏离可接受路线后掉多少分
- `conversion_horizon_plies`
  - 需要多少 ply 才能把优势转成更稳定、更明显的收益

### Acceptable line draft definition

先给一个工程上容易落地的版本：

某条后续线如果同时满足：

- 保留至少 `70%` 的初始收益
- 且相对同层最优线不差超过 `80 cp`

就记为 `acceptable`

这个定义后面可以调，但先用它能把“容易兑现”和“必须极度精确”区分开。

### Suggested analysis questions

- 在引擎可接受的多个候选步里，`Maia` 是否更偏好 realizability 高的步
- 真人实际走法是否系统性偏向 realizability 高的选择
- 这种偏向是否在复杂局面里更明显
- 这种偏向是否随 Elo 提升而减弱

### First implementation strategy

先做两层：

1. `feature table`
   - 不急着合成总分
2. `optional scalar score`
   - 后面如果需要网站排序或回归模型，再做归一化总分

### Proposed artifact layout

```text
outputs/analyses/<analysis_id>/
  realizability/
    candidate_feature_table.csv
    position_summary.csv
    maia_alignment.csv
    metadata/
      summary.json
      summary.md
```

### Detailed v0 draft

完整的 `v0` 指标草案单独写在这里：

- [realizability_metric_v0.md](/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/docs/experiments/realizability_metric_v0.md)

这份文档已经把下面几层明确写出来了：

- 候选步筛选
- `T_viable` 的定义
- `acceptable move` 的定义
- 特征表字段
- 一个便于排序和网页展示的 `realizability_score_v0`

## Recommended implementation order

建议的顺序是：

1. `Experiment 1`
   - 最独立，最容易复用现有 pipeline
2. `Experiment 2`
   - 能快速回答“复杂局面是不是确实更难预测”
3. `Experiment 3`
   - 研究价值最大，但定义工作也最多

## Repository scaffolding added for these experiments

- `configs/experiments/stockfish_time_budget_sweep.template.yaml`
- `configs/experiments/rank_bucket_comparison.template.yaml`
- `configs/experiments/realizability_probe.template.yaml`
- `scripts/analysis/README.md`
- `outputs/analyses/README.md`

## What we should implement next

下一步最自然的是先做 `Experiment 1`：

- 输入已经准备好
- 不依赖新的模型
- 只需要复用复杂局面表 + Stockfish
- 可以先跑小样本，再夜间跑 `60s` 档
