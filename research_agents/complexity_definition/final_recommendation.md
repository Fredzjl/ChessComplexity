# Final Recommendation

## 1. Recommended Main Definition: `complexity v1`

### Primary object

- `Theory judgment`
  - Define `complexity v1` at `move-level`:
    - `C_v1(p, m)`
  - Then derive position-level summaries from it when needed.

### Name

- `Continuation Burden Complexity`
- shorthand: `CBC-v1`

### Definition

For root position `p` and candidate move `m`:

1. Build a shallow continuation tree under strong opponent replies and root-player follow-ups.
2. Define an acceptable set at each later root-player decision node:

`A(n ; p, m) = { a : E(n, a) >= max(E*(n) - delta_local, T_viable(p, m)) }`

with:

`T_viable(p, m) = max(E(p, m) - Delta_drop, E(p) + rho * max(E(p, m) - E(p), 0), F_abs)`

3. Compute raw burden features:

- `f_width = mean 1 / max(1, |A|)`
- `f_unique = mean I[|A| <= 2]`
- `f_refute = mean I[opponent can force next |A| = 0]`
- `f_drop = median cutoff-drop below acceptability`
- `f_streak = normalized longest narrow streak`

4. Normalize each raw feature by empirical CDF on a calibration corpus.
5. Average them equally:

`C_v1(p, m) = 100 * mean(z_width, z_unique, z_refute, z_drop, z_streak)`

No manual weights.

### Why this is the recommended main definition

- it directly models the burden that motivates the project
- it is candidate-specific, so it can explain why humans avoid the engine best move
- it is decomposable into interpretable reasons
- it can reuse most of the current `realizability` infrastructure

### Position-level derived summaries

Recommended derived views:

- `C_v1_best(p) = C_v1(p, m_sf_best)`
- `C_v1_frontier(p) = mean_{m in K(p)} C_v1(p, m)`

Use:
- `best` for “is the engine best move humanly difficult?”
- `frontier` for “is this position broadly difficult?”

## 2. Recommended Simplified Definition: `complexity v1-lite`

### Name

- `Immediate Burden Complexity`
- shorthand: `IBC-lite`

### Definition

Keep the same acceptable-set logic, but only inspect the first root-player re-decision after each strong opponent reply.

Raw features:

- `g_width = mean 1 / max(1, |A_d1|)`
- `g_unique = mean I[|A_d1| <= 2]`
- `g_refute = mean I[|A_d1| = 0]`

Scalar:

`C_v1_lite(p, m) = 100 * mean(F_D(g_width), F_D(g_unique), F_D(g_refute))`

Equal weights only.

### Why keep this lighter version

- cheaper to compute
- easier to deploy on large samples
- still directly tied to “do I get a comfortable next move after the opponent resists?”
- good as a first-pass filter before running full `CBC-v1`

## 3. Why Not Use the Current Simple Metric as v1

- `Code-validated result`
  - the current root-only score does track real effects:
    - actual human moves rank worse in high-complexity positions
    - high-complexity positions show more Stockfish budget instability
    - engine-best / Maia-reluctant cases are more frequent in high-complexity positions
- `Code-validated result`
  - but the signal is incomplete:
    - complexity-score bucket trends are present, yet the direct correlation with Stockfish switch count is only `0.0831`
- `Theory judgment`
  - the current score mainly measures root branching under Maia
  - it does not directly encode “how narrow is the continuation after I choose this move?”

## 4. Why Not Reuse the Current Realizability Scalar as v1

- `Theory judgment`
  - the current scalar in `src/analysis/realizability.py` is a good scaffold, not a final research definition
- main issue:
  - it uses manual subfeature weights
- recommendation:
  - keep the raw features
  - replace the scalar with equal-weight empirical-CDF aggregation
  - calibrate acceptable-set thresholds statistically

## 5. Recommended Calibration Rules

Do:

- choose threshold hyperparameters from a declared grid
- split by game
- optimize a fixed validation objective
- keep equal weights in the final scalar

Do not:

- choose cp thresholds by taste after seeing examples
- introduce unexplained coefficients
- tune separately on each sample you report

Bootstrap fallback if calibration is not yet implemented:

- `rho = 0.70`
- `Delta_drop = 120 cp`
- `F_abs = 80 cp`
- `delta_local = 80 cp`

Status:
- `Theory judgment`
  - these fallback values are acceptable for a bootstrap run because they already exist in repo logic
- `Unverified hypothesis`
  - final calibrated values will improve predictive utility

## 6. How Complexity and Realizability Should Coexist

Recommended separation:

- `complexity`
  - broad difficulty descriptor
  - can be position-level, move-level, or line-level
- `realizability`
  - narrower question:
    - “given this advantageous move, how easy is it to convert?”

Operational unification:

- for positive-gain candidate moves:
  - `realizability_v1(p, m) = 100 - complexity_v1(p, m)`
  - only if both are built from the same burden features and normalization set

Why this is safe:

- same raw mechanics
- opposite semantics
- no need to maintain two separate feature pipelines

Why this should still be reported separately:

- the semantic question differs
- some moves are complex without representing a convertible advantage

## 7. Recommended Next Steps

1. Refactor the current `realizability` feature extractor so raw burden features are first-class outputs.
2. Add a config-driven scalarizer:
   - empirical CDF normalization
   - equal-weight averaging only
3. Run the four validation experiments in `experiment_plan.md`.
4. Compare:
   - current `simple_metric`
   - `IBC-lite`
   - `CBC-v1`
5. Promote the winner into the main pipeline and review site.

## 8. Final Bottom Line

- `Theory judgment`
  - Use `move-level Continuation Burden Complexity` as the main definition.
- `Theory judgment`
  - Use `v1-lite` when compute budget is tight.
- `Code-validated result`
  - the repository already contains evidence that the motivating phenomena are real.
- `Unverified hypothesis`
  - a calibrated move-level burden metric will be more useful for `human-like chess model` research than the current root-only complexity score.
