# Chess Complexity Full Test

Repository scaffold for a first end-to-end experiment on human-like middlegame complexity.

This scaffold does not download data, install models, or run inference yet. It only prepares:

- a clean project layout
- the first-pass metric definition
- artifact destinations
- step-by-step automation prompts and checks

## Scope of the first full test

- Download 10 Lichess standard games
- Install Maia-2 and verify local inference
- Inspect only middlegame positions from fullmoves 10 through 30
- Skip positions when either side has fewer than 8 remaining pieces
- Compute a simple 3-ply complexity score from Maia-2 move probabilities
- Save all intermediate artifacts, including policy distributions and per-position outputs
- Render selected complex positions to PNG for visual review

## Provisional complexity metric

For a candidate position:

1. Run Maia-2 and keep moves with probability `>= 0.10`
2. Expand the tree for 3 plies
3. Count the number of probability-qualified move edges in that 3-ply tree
4. Mark a position as `high_complexity` when the score is `>= 10`

This threshold is intentionally simple and easy to audit. It can be changed later without reshaping the repository.

## Repository layout

```text
chess-complexity-full-test/
  apps/
  automations/
  configs/
  data/
  docs/
  models/
  outputs/
  scripts/
  src/
  tests/
  apps/review-site/
  docs/experiments/
  outputs/analyses/
  scripts/analysis/
  scripts/pipeline/
  scripts/review/
  scripts/setup/
```

## Directory roles

- `apps/`: frontend or analyst-facing tools, such as the review website prototype
- `configs/experiments/`: reusable experiment templates for different scales or cohorts
- `data/raw|interim|processed/`: inputs and derived datasets, organized by reproducibility stage
- `docs/experiments/`: follow-up experiment specs, assumptions, and research notes
- `outputs/analyses/`: reproducible derived analysis results for large-sample follow-up studies
- `outputs/runs/`: pipeline-stage outputs tied to one concrete run
- `outputs/reviews/`: curated review bundles for human inspection
- `outputs/sites/`: generated static websites for browsing results
- `scripts/analysis/`: entrypoints for research analyses that sit on top of completed runs
- `scripts/pipeline/`: dataset parsing, filtering, inference, and scoring entrypoints
- `scripts/review/`: review bundle and visualization entrypoints
- `scripts/setup/`: environment and model verification entrypoints

## Where to start later

Use the prompt files in `automations/prompts/` in order. The main checklist lives in `automations/checklist.md`.

The current repository also keeps compatibility wrappers in `scripts/` so old commands still work while the canonical structure shifts to the subdirectories above.

## Planned follow-up analyses

Three larger follow-up experiment tracks are now scoped and documented:

- `Stockfish time-budget sweep on complex positions`
  - study whether engine recommendations stay stable when the same complex position is re-analysed under short versus long think times
- `Actual-move rank comparison by Elo bucket`
  - compare how well Maia and Stockfish rank the human move on all positions versus complex-only positions
- `Realizability / convertibility metric`
  - measure whether an engine-favored advantage is easy for a human to convert without a brittle chain of unique moves

Start from:

- [docs/experiments/README.md](/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/docs/experiments/README.md)
- [configs/experiments/stockfish_time_budget_sweep.template.yaml](/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/configs/experiments/stockfish_time_budget_sweep.template.yaml)
- [configs/experiments/rank_bucket_comparison.template.yaml](/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/configs/experiments/rank_bucket_comparison.template.yaml)
- [configs/experiments/realizability_probe.template.yaml](/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/configs/experiments/realizability_probe.template.yaml)
