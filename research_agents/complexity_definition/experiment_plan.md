# Experiment Plan

## 1. Goal

Turn the complexity discussion into a reproducible validation loop that serves downstream `human-like model` work.

## 2. Validation Principles

- do not evaluate only one scalar
- always keep raw subfeatures
- separate `calibration`, `validation`, and `reporting`
- prefer equal-weight aggregation or statistically fitted transforms
- never introduce unexplained manual weights

## 3. Existing Evidence Already Verified

Artifacts used:
- `outputs/sites/20260509_balanced_100_games/site/data/site_bundle.json`
- `outputs/analyses/20260510_stockfish_time_budget_overnight_1800/stockfish_time_budget/root_analysis_by_budget.jsonl`
- repository reports under `outputs/reports/`

Derived by:
- `scripts/analyze_existing_artifacts.py`

### Verified fact A: complex positions degrade actual-move ranking

- `Code-validated result`
  - Maia mean actual-move rank is worse in `high_complexity` than `non_high_complexity`
  - Stockfish top-20 actual-move rank is also worse in `high_complexity`

Why this matters:
- the current score is not nonsense
- but it does not prove the current score is the best definition

### Verified fact B: Stockfish changes its mind a lot inside the complex subset

- `Code-validated result`
  - in the existing `1800` complex-position budget sweep, `65%` of positions show at least one best-move switch across budgets
  - switch rate rises from `0.5595` in score bucket `10-19` to `0.7256` in bucket `40+`

Why this matters:
- engine instability is a real signal
- but the weak correlation means current `simple_metric` only partially captures it

### Verified fact C: strong-engine / Maia-reluctant moves exist

- `Code-validated result`
  - among current strong-engine positions (`Stockfish >= +3.00`), `29.06%` are Maia-reluctant
  - that rate rises to `31.07%` inside `high_complexity`

Why this matters:
- the motivating phenomenon is present in current data

## 4. Core Validation Suite for New Metrics

## Experiment A: Complex vs Non-Complex Actual-Move Ranking

Question:
- do higher-complexity slices make actual human moves harder for Maia and/or Stockfish to rank well?

Objects:
- `C_pos`
- derived from each candidate family

Data:
- current parsed positions
- current Maia root probabilities
- current Stockfish root analysis

Protocol:

1. Score all eligible positions with the candidate complexity metric.
2. Form slices:
   - bottom quartile
   - middle two quartiles
   - top quartile
   - optional binary threshold for site compatibility
3. For each slice, compute:
   - `mean_actual_rank`
   - `median_actual_rank`
   - `hit@1`
   - `hit@3`
   - `hit@5`
   - coverage for Stockfish top-`K`
4. Compare Maia and Stockfish side by side.

Primary acceptance signal:
- top-complexity slice should show clearly worse actual-move ranks than bottom-complexity slice

Recommended outputs:
- `rank_by_metric_quantile.csv`
- `rank_by_metric_quantile.md`
- `chart_ready_long.csv`

## Experiment B: Stockfish Time-Budget Instability

Question:
- do positions scored as more complex also exhibit more engine instability across time budgets?

Objects:
- mainly `C_pos`
- optionally `C_pos_best(p) = C_move(p, m_sf_best)`

Data:
- existing overnight sweep for complex positions
- optional extension sweep for a matched non-complex control sample

Protocol:

1. For each position, compute:
   - `best_move_switch_count`
   - `unique_best_move_count`
   - `best_score_range_cp`
   - `adjacent_topk_overlap`
   - `pv_prefix_stability`
2. Correlate each metric with the candidate complexity score.
3. Bucket by complexity quantiles and compare means.
4. If budget allows, add a matched non-complex control set.

Primary acceptance signal:
- more complex slices should show more switching and lower top-`K` overlap

Important note:
- current evidence already supports the phenomenon inside the complex subset
- the missing piece is a stronger metric than the current root-only score

Recommended outputs:
- `time_budget_vs_metric.csv`
- `time_budget_bucketed_summary.csv`
- `time_budget_validation.md`

## Experiment C: Engine-Best but Maia-Unlikely

Question:
- does the metric isolate positions where Stockfish strongly recommends a move that Maia thinks humans rarely choose?

Objects:
- `C_pos_best`
- `C_move(p, m_sf_best)`

Data:
- Stockfish root best move and margin
- Maia probability of that move
- optional actual human move

Protocol:

1. Restrict to positions with Stockfish root best score margin above a preset floor.
2. Mark a position as `Maia-reluctant` when Maia probability of the Stockfish best move is low.
3. Compare complexity distributions between reluctant and non-reluctant subsets.
4. Optional logistic model:
   - target: `Maia-reluctant`
   - predictor: candidate complexity

Primary acceptance signal:
- higher complexity should increase the rate of Maia reluctance

Recommended outputs:
- `engine_best_maia_reluctance_by_metric.csv`
- `engine_best_examples.json`

## Experiment D: Move-Level Human Preference Within the Same Position

Question:
- when several near-best candidate moves exist, do humans and Maia prefer lower-burden candidates?

Objects:
- `C_move(p, m)`

Data:
- root candidate set
- move-level complexity for each candidate
- actual human move
- Maia root probabilities

Protocol:

1. Build a candidate set per position:
   - near-best by cp window, or
   - top-`K` root candidates
2. Compute `C_move(p, m)` for each candidate.
3. Within each position:
   - compare actual human move complexity to engine-best complexity
   - compare Maia probability with complexity rank
4. Summarize:
   - fraction where human chooses a lower-complexity candidate than Stockfish best
   - Spearman correlation between `-complexity` and Maia probability

Primary acceptance signal:
- humans and Maia should lean toward lower-burden candidates when evaluation difference is small

Recommended outputs:
- `candidate_level_complexity_table.csv`
- `within_position_preference_summary.json`

## 5. Calibration Plan

The biggest risk is choosing “acceptable line” thresholds by taste. Do not do that.

### Parameters to calibrate

- `rho` in the viability floor
- `Delta_drop`
- `F_abs`
- `delta_local`
- continuation horizon `H`

### Calibration protocol

1. Split by `game_id`, not by position.
2. Use a fixed search grid declared in config.
3. Optimize one predefined objective on the training split.

Recommended objective:
- maximize separation between:
  - `actual human did not play Stockfish best`
  - `actual human did play Stockfish best`
  among positions where the Stockfish best move is clearly valuable

Secondary objective:
- maximize within-position correlation between lower complexity and higher Maia probability

### Aggregation rule

- raw features stay raw
- scalar uses either:
  - equal-weight mean after empirical CDF normalization, or
  - a single statistically fitted combination declared in advance

Default recommendation:
- equal-weight mean after empirical CDF normalization

## 6. Deliverables for the Next Iteration

Minimum:

- a config-driven `CBC` scorer
- candidate-level CSV
- position-level derived CSV
- validation notebooks or scripts
- one summary Markdown report

Nice to have:

- review-site integration for move-level explanations
- “why complex?” tooltip from `width / unique / refute / drop / streak`

## 7. Decision Rule

A new complexity metric is worth adopting if:

1. it outperforms the current root-only score on Experiment A
2. it has a clear positive relationship with Experiment B instability features
3. it isolates the Experiment C Maia-reluctant phenomenon better than the current score
4. it remains interpretable at candidate level

## 8. Current Status

- `Code-validated result`
  - the repository already contains enough saved artifacts to verify the three required phenomena at a lightweight level
- `Unverified hypothesis`
  - a calibrated `CBC` implementation will materially outperform the current `simple_metric`
