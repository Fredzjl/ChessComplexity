# Realizability Metric v0

这份文档把实验三的“可实现度”先定成一个可以落地、可以修改、也可以拆解解释的第一版指标。

目标不是一次性得到最终定义，而是先得到一个：

- 语义清楚
- 工程上能实现
- 后面容易替换参数和公式

的 `v0` 版本。

## 1. 核心问题

我们不是在问：

- “这步强不强？”

而是在问：

- “这步带来的优势，人类是不是容易兑现？”

更具体一点：

- 如果一着棋在引擎看来很好，但后面必须连续多步唯一或唯二，稍有偏差就掉光优势，那么它的 `realizability` 应该低
- 如果一着棋虽然同样有优势，但后续存在多条自然、安全、容错率高的兑现路径，那么它的 `realizability` 应该高

## 2. 评估对象

`realizability` 的基本对象应该是：

- `candidate move level`

也就是：

- 在某个局面 `p`
- 对某一个候选步 `m`

计算 `R(p, m)`

而不是先做 position-level 的一个总分。

原因很简单：

- 后面你要研究的是 `Maia` 和真人是否更偏向那些“更容易兑现”的选择
- 这个问题天然是“候选步之间”的比较，不是单个局面的整体属性

## 3. v0 的直觉定义

给定局面 `p` 和候选步 `m`：

如果 `m` 走出后，后续满足下面这些条件，那么 `R(p, m)` 应该高：

- 保住优势的后续走法不止一条
- 对手即便有多个回复，也不容易立刻把你的优势压没
- 你自己的下一次、下下次决策都有多种“差不多都行”的选择
- 即使不走最精确的唯一手，也不会立刻掉很多分
- 兑现优势的路径不需要特别长

反过来，`R(p, m)` 低通常意味着：

- 后续线非常窄
- 唯一手或唯二手负担很重
- 一旦偏离，掉分很快
- 对手有很多方式把你拖进精确计算

## 4. 数学对象和记号

记：

- `p`
  - 当前局面
- `s`
  - 当前走棋方，也就是 root player
- `m`
  - `s` 在 `p` 上的候选步
- `E(p)`
  - 引擎对局面 `p` 的评估，统一转换成 `s` 的视角
- `E(p, m)`
  - `s` 在 `p` 走 `m` 之后的评估
- `E_best(p)`
  - `p` 上最佳步对应的评估

后面所有评估都统一成：

- `root side POV`

也就是说，不管轮到谁走，分数都用 root player `s` 的收益来表达。

## 5. 候选步集合

不是所有合法步都要进 realizability 分析。先只分析“引擎觉得值得考虑”的步。

### v0 候选步筛选

对局面 `p`，定义候选集合 `C(p)` 为满足下面条件之一的步：

1. `E(p, m) >= E_best(p) - near_best_window_cp`
2. `E(p, m) >= absolute_advantage_floor_cp`
3. `E(p, m) - E(p) >= min_incremental_gain_cp`

### 推荐默认值

- `near_best_window_cp = 80`
- `absolute_advantage_floor_cp = 150`
- `min_incremental_gain_cp = 80`

### 为什么这样筛

- 第 1 条保留“接近最佳”的实战候选步
- 第 2 条保留“本身已经明显有利”的步
- 第 3 条保留“虽然不一定已经大优，但确实显著改善了局面”的步

## 6. 可接受后续线的定义

这是 `v0` 里最核心的部分。

### 6.1 根步初始价值

先定义候选步 `m` 的初始价值：

- `V0 = E(p, m)`

再定义它带来的增益：

- `G0 = E(p, m) - E(p)`

### 6.2 可兑现阈值

对后续树中的任意节点 `n`，定义该节点仍算“可兑现”的最低要求：

`T_viable(n; p, m) = max(absolute_floor, V0 - max_total_drop_cp, E(p) + retain_gain_ratio * max(G0, 0))`

### 直觉解释

后续局面要继续算“还在兑现这步的优势”，至少要满足三件事里的最严格者：

1. 不能跌到一个绝对过低的优势水平之下
2. 不能比候选步刚走出时掉太多
3. 不能把最初获得的改善几乎全吐回去

### 推荐默认值

- `absolute_floor = +80 cp`
- `max_total_drop_cp = 120 cp`
- `retain_gain_ratio = 0.70`

## 7. 节点上的“可接受走法”

现在定义某个节点 `n` 上一着后续步 `a` 是否 `acceptable`。

记：

- `E*(n)`
  - 在节点 `n` 上，当前走棋方最佳可分析步的 root-side 评估
- `E(n, a)`
  - 在节点 `n` 走 `a` 后的 root-side 评估

那么 `a` 被视为 `acceptable`，当且仅当：

`E(n, a) >= max(E*(n) - local_slack_cp, T_viable(n; p, m))`

### 含义

某步要被当成“还算能兑现”：

- 不能离该节点最优选择太远
- 也不能让整条兑现路径跌破“还算保住原始优势”的底线

### 推荐默认值

- `local_slack_cp = 80`

## 8. 树展开方式

### v0 推荐

- root 候选步之后继续展开 `H = 4` plies
- 每个节点只分析 `MultiPV = 8` 到 `12`
- 节点分析时间先用固定 budget
  - 比如 `500 ms` 或 `1000 ms`

### 为什么不是更深

`v0` 先追求：

- 能算得动
- 结构解释清楚

不是追求理论完美。

如果 `v0` 就直接上很深的树，成本会非常高，而且很多定义问题还没固定。

## 9. v0 特征定义

先做特征表，不急着先压成一个最终分数。

## 9.1 Root-level features

### `root_value_cp`

- `root_value_cp = E(p, m)`

### `initial_gain_cp`

- `initial_gain_cp = E(p, m) - E(p)`

### `distance_from_best_cp`

- `distance_from_best_cp = E_best(p) - E(p, m)`

这个特征主要用于后面比较：

- 某步虽然不是最优，但如果 realizability 很高，人类是否更偏向它

## 9.2 Flexibility features

### `acceptable_width_player_mean`

在所有 root player 的后续决策节点上：

- `acceptable` 走法数的平均值

### `acceptable_width_player_min`

在所有 root player 的后续决策节点上：

- `acceptable` 走法数的最小值

### `acceptable_width_player_d1`

在 root player 第一次再次决策时：

- `acceptable` 走法数

这个特征很好理解，也很贴近“人会不会觉得顺手”。

## 9.3 Opponent-pressure features

### `survival_rate_after_opponent`

在所有已分析的对手回复里，统计：

- 有多少比例的对手回复之后，root player 仍然至少有 `1` 步 acceptable reply

定义：

`survival_rate_after_opponent = (# opponent replies after which player still has >=1 acceptable move) / (# analyzed opponent replies)`

如果这个值低，说明对手很容易把你逼进崩塌区。

### `opponent_refutation_density`

对手的已分析回复里，有多少比例会让局面立刻跌破 `T_viable`

这个值越高，realizability 越低。

## 9.4 Narrowness / burden features

### `unique_burden_plies`

在整棵后续树里，对 root player 的决策节点统计：

- `acceptable width <= 2`

的 ply 数量

这表示“你后面经常只有唯一或唯二选择”。

### `longest_narrow_streak`

root player 连续处于窄路径状态的最长长度

这个特征比总数量更能体现“是不是一整段都必须精算”。

## 9.5 Fragility features

### `deviation_penalty_cp_mean`

在 root player 的各个决策节点：

- 取“最优 acceptable move”和“最好但不 acceptable 的 move”之间的差值
- 再做平均

直觉上：

- 如果一旦离开 acceptable 区域就要掉很多分，这条线很脆

### `deviation_penalty_cp_max`

同样的差值取最大值

这个特征用来抓“某一步一错就崩”的点。

## 9.6 Conversion-speed features

### `conversion_horizon_plies`

定义一个“明显兑现”的阈值：

- 例如 `conversion_target_cp = max(250 cp, V0 + 80 cp)`

然后看最早在哪个 ply 能达到这个水平并维持不掉出 viable 区。

如果在 horizon 内达不到，则记为：

- `conversion_horizon_plies = H + 1`

### `conversion_success_within_horizon`

- 布尔值

表示在当前 horizon 内能不能明显兑现。

## 10. 可实现度总分 v0

我建议 `v0` 先保留所有特征，同时给一个辅助性的总分，方便排序和后续网页展示。

## 10.1 先归一化成子分量

### Flexibility

`F_width = clip(acceptable_width_player_mean / width_target, 0, 1)`

推荐：

- `width_target = 4`

### Survival

`F_survival = survival_rate_after_opponent`

### Slack

定义平均余量：

- `mean_margin_to_viable_cp`

表示 acceptable 线平均比 `T_viable` 高多少

归一化：

`F_slack = clip(mean_margin_to_viable_cp / slack_target_cp, 0, 1)`

推荐：

- `slack_target_cp = 120`

### Uniqueness risk

`R_unique = clip(unique_burden_plies / burden_cap_plies, 0, 1)`

推荐：

- `burden_cap_plies = 4`

### Fragility risk

`R_fragile = clip(deviation_penalty_cp_mean / penalty_cap_cp, 0, 1)`

推荐：

- `penalty_cap_cp = 200`

### Slow-conversion risk

`R_slow = clip((conversion_horizon_plies - 1) / horizon_plies, 0, 1)`

## 10.2 总分公式

`realizability_score_v0 = 100 * (0.28 * F_width + 0.22 * F_survival + 0.12 * F_slack + 0.18 * (1 - R_unique) + 0.15 * (1 - R_fragile) + 0.05 * (1 - R_slow))`

### 解释

- `F_width`
  - 你自己有多少“都还行”的选择
- `F_survival`
  - 对手有没有很多办法把你拉出可兑现区
- `F_slack`
  - acceptable 路径是不是还留着余量
- `R_unique`
  - 是否要连续多步唯一/唯二
- `R_fragile`
  - 一旦走偏掉多少
- `R_slow`
  - 优势是否需要很长时间才兑现

## 11. 语义区间

为了后面方便审阅，先给一个语义分段：

- `80-100`
  - 很容易兑现
- `60-79`
  - 实战可行，但有一些精确要求
- `40-59`
  - 中等脆弱
- `20-39`
  - 明显脆弱，需要较精确
- `0-19`
  - 极度脆弱，接近“引擎线”

## 12. 和 Maia / 真人行为的连接方式

实验三真正想回答的问题，不是“分数好不好看”，而是：

- 在同一局面多个引擎认可的候选步里，`Maia probability` 是否更偏向 `realizability` 高的步
- 真人实际走法是否也更偏向 `realizability` 高的步

所以后面建议至少做 3 张表：

### `candidate_feature_table.csv`

每一行是一个 `(position, candidate move)`：

- `position_id`
- `candidate_uci`
- `candidate_san`
- `root_value_cp`
- `initial_gain_cp`
- `distance_from_best_cp`
- `acceptable_width_player_mean`
- `acceptable_width_player_min`
- `survival_rate_after_opponent`
- `unique_burden_plies`
- `deviation_penalty_cp_mean`
- `conversion_horizon_plies`
- `realizability_score_v0`
- `maia_probability`
- `maia_rank`
- `human_played`

### `position_summary.csv`

每个局面上：

- 最佳引擎步的 realizability
- 真人步的 realizability
- `Maia top-1` 的 realizability
- 各候选间 realizability gap

### `maia_alignment.csv`

用于后面直接做相关性或回归：

- `maia_probability ~ realizability_score_v0`
- 可分 Elo bucket、复杂度 bucket、time control

## 13. 这个 v0 版本的优点

- 可解释
- 可拆解
- 容易在网页里做 drill-down
- 适合后面直接和 `Maia`、真人着法对齐

## 14. 这个 v0 版本的局限

### 它依赖固定搜索 horizon

如果 horizon 太短，会低估一些慢兑现但其实很稳的线。

### 它依赖 MultiPV 截断

如果某个好步没进候选，就会让宽度估计偏窄。

### 它把“可接受”定义成了 engine-centered

这很好做，但不一定完全等于“人类觉得自然”。

## 15. 我建议你后面优先会改的地方

如果后面要继续打磨，这 5 个地方最值得先动：

1. `T_viable` 的定义
2. `local_slack_cp`
3. `retain_gain_ratio`
4. `unique_burden_plies` 是不是只统计 root player 节点
5. 总分权重是不是要学出来，而不是手工给

## 16. v0 的一句话总结

`realizability_score_v0` 不是在衡量“这步强不强”，而是在衡量：

- 这步创造出来的优势
- 在有限计算、存在失误风险的真实人类实战里
- 是否有足够宽、足够稳、足够自然的兑现路径
