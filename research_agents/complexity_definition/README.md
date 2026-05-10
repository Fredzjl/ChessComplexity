# Complexity Definition Research Package

This directory contains a self-contained research package for defining a human-centered chess complexity metric inside the current repository.

## What This Package Does

- distinguishes `position-level`, `move-level`, and `line-level` complexity
- proposes multiple computable metric families instead of one hand-wavy score
- recommends one `complexity v1` main definition and one `v1-lite` fallback
- records which claims are:
  - `Theory judgment`
  - `Code-validated result`
  - `Unverified hypothesis`
- includes a lightweight script that reuses existing repository artifacts instead of rerunning heavy inference

## Files

- `metric_candidates.md`
  - object-level analysis and candidate metric families
- `experiment_plan.md`
  - validation experiments, calibration procedure, and artifact plan
- `final_recommendation.md`
  - recommended `v1` and `v1-lite`
- `scripts/analyze_existing_artifacts.py`
  - summarizes already-saved site and analysis artifacts
- `results/existing_artifact_validation.md`
  - human-readable validation summary
- `results/rank_by_complexity.csv`
  - actual-move rank comparison: complex vs non-complex
- `results/time_budget_by_complexity_bucket.csv`
  - Stockfish instability summary across time budgets
- `results/engine_best_maia_reluctance_by_slice.csv`
  - engine-best but Maia-reluctant phenomenon by slice

## Key Takeaways

- `Theory judgment`
  - The main research object should be `move-level complexity`, because the motivating question is not just “is this position messy?” but “if I choose this candidate move, how hard is it for a human to justify and realize?”
- `Code-validated result`
  - In the existing `100-game` bundle, actual human moves rank worse in `high_complexity` positions than in `non_high_complexity` positions for both Maia and Stockfish.
  - In the existing `1800-position` Stockfish budget sweep, best-move switching across budgets is common inside the complex subset.
  - Strong Stockfish recommendations that Maia assigns low probability do exist, and they are more common in the current high-complexity subset.
- `Unverified hypothesis`
  - A move-level “continuation burden” metric should explain human avoidance better than the current root-only `simple_metric`.

## Why This Is Not Just Realizability Renamed

- `Theory judgment`
  - `Realizability` asks whether the value of a specific move can be converted by a human.
  - `Complexity` is broader: it can live on a position, a move, or a line, and it includes instability, branching burden, and human-engine disagreement.
  - For advantage-bearing candidate moves, `high complexity` and `low realizability` are closely related, but they should not be collapsed into the same label.

## Current Empirical Snapshot

From `results/existing_artifact_validation.md`:

- `Code-validated result`
  - Maia mean actual-move rank: `2.9527` in `high_complexity` vs `2.2759` in `non_high_complexity`
  - Stockfish mean actual-move rank: `4.4904` in `high_complexity` vs `2.8818` in `non_high_complexity`
  - In the `complex` time-budget subset, `65%` of positions show at least one Stockfish best-move switch across budgets
  - Among strong-engine positions (`Stockfish >= +3.00`), `29.06%` are Maia-reluctant overall, rising to `31.07%` inside `high_complexity`

## Recommended Reading Order

1. `metric_candidates.md`
2. `experiment_plan.md`
3. `final_recommendation.md`
4. `results/existing_artifact_validation.md`
