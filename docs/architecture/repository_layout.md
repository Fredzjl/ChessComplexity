# Repository Layout

## Goal

Keep the repository usable when the project grows from a 10-game prototype into large batches of positions, multiple model variants, and repeated human-review cycles.

## Recommended top-level structure

```text
apps/
  review-site/
automations/
configs/
  experiments/
data/
  raw/
  interim/
  processed/
  manifests/
  samples/
docs/
  architecture/
  experiments/
  runbooks/
models/
outputs/
  analyses/
  runs/
  reviews/
  sites/
  reports/
scripts/
  analysis/
  setup/
  pipeline/
  review/
src/
  analysis/
tests/
```

## Design principles

- Separate computation outputs from human-facing deliverables.
- Keep raw inputs reproducible and immutable.
- Treat websites and review bundles as exported artifacts, not as pipeline internals.
- Group entrypoints by workflow so future teammates can find the right script family quickly.
- Preserve thin compatibility wrappers while the project is still evolving rapidly.
- Reserve a separate home for follow-up analyses that are more research-oriented than pipeline-oriented.

## What belongs where

- `outputs/runs/`
  - per-stage or per-experiment computation outputs
- `outputs/reviews/`
  - curated tables and images meant for manual inspection
- `outputs/sites/`
  - static web apps generated from run outputs
- `outputs/analyses/`
  - reproducible follow-up experiment results, usually tables and derived metrics
- `outputs/reports/`
  - notebooks, slides, or one-off external deliverables

## Migration note

The current repository still contains some historical MVP outputs under `outputs/runs/` because those artifacts were generated before the larger directory convention was introduced. New large-scale experiments should follow the new split.
