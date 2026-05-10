# Artifact Schema

All experiment outputs should be grouped by `run_id`.

## Run directory

`outputs/runs/<run_id>/`

## Expected files

- `metadata/run_summary.json`
  - top-level counts, timestamps, config snapshot, model metadata
- `metadata/position_filtering.csv`
  - one row per candidate position with skip reasons
- `policy/raw_policy_snapshots.jsonl`
  - one line per queried position or tree node
- `policy/topk_policy_snapshots.csv`
  - flattened top-k probabilities for quick inspection
- `complexity/position_scores.csv`
  - final score table for all eligible positions
- `complexity/high_complexity_positions.csv`
  - subset flagged by the threshold
- `images/<position_id>.png`
  - board image for each flagged position
- `logs/pipeline.log`
  - human-readable execution log

## Position identifier

Use a stable identifier format:

`<game_id>_ply_<ply_index>`

Example:

`eEZHeIt9_ply_37`
