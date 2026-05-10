#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${1:-publish/review-site-github-pages}"

if command -v conda >/dev/null 2>&1; then
  PYTHON_CMD=(conda run -n chess-complexity python)
elif [ -x "/opt/homebrew/Caskroom/miniforge/base/bin/conda" ]; then
  PYTHON_CMD=(/opt/homebrew/Caskroom/miniforge/base/bin/conda run -n chess-complexity python)
else
  PYTHON_CMD=(python3)
fi

"${PYTHON_CMD[@]}" "${REPO_ROOT}/scripts/review/build_review_site.py" \
  --output-dir "${OUTPUT_DIR}" \
  --games-csv "${REPO_ROOT}/outputs/runs/20260509_balanced_100_games/step_04_parse_filter/parsed/games.csv" \
  --parsed-positions-csv "${REPO_ROOT}/outputs/runs/20260509_balanced_100_games/step_04_parse_filter/parsed/positions.csv" \
  --position-scores-csv "${REPO_ROOT}/outputs/runs/20260509_balanced_100_games/step_07_complexity_scoring/complexity/position_scores.csv" \
  --raw-policy-jsonl "${REPO_ROOT}/outputs/runs/20260509_balanced_100_games/step_06_policy_expansion/policy/raw_policy_snapshots.jsonl" \
  --run-summary-json "${REPO_ROOT}/outputs/sites/20260509_balanced_100_games/metadata/site_build_summary.json" \
  --stockfish-analysis-json "${REPO_ROOT}/outputs/analyses/20260510_rank_bucket_comparison_100_games/rank_bucket_comparison/cache/stockfish_root_analysis.json" \
  --time-budget-summary-json "${REPO_ROOT}/outputs/analyses/20260510_stockfish_time_budget_overnight_1800/stockfish_time_budget/metadata/summary.json" \
  --time-budget-position-stability-csv "${REPO_ROOT}/outputs/analyses/20260510_stockfish_time_budget_overnight_1800/stockfish_time_budget/tables/position_stability.csv" \
  --time-budget-root-analysis-csv "${REPO_ROOT}/outputs/analyses/20260510_stockfish_time_budget_overnight_1800/stockfish_time_budget/tables/root_analysis_by_budget.csv" \
  --rank-bucket-summary-json "${REPO_ROOT}/outputs/analyses/20260510_rank_bucket_comparison_100_games/rank_bucket_comparison/metadata/summary.json" \
  --rank-bucket-bucket-summary-csv "${REPO_ROOT}/outputs/analyses/20260510_rank_bucket_comparison_100_games/rank_bucket_comparison/tables/bucket_summary.csv" \
  --realizability-summary-json "${REPO_ROOT}/outputs/analyses/20260510_realizability_probe_100_games/realizability_probe/metadata/summary.json" \
  --realizability-bucket-summary-csv "${REPO_ROOT}/outputs/analyses/20260510_realizability_probe_100_games/realizability_probe/tables/elo_bucket_summary.csv" \
  --realizability-position-summary-csv "${REPO_ROOT}/outputs/analyses/20260510_realizability_probe_100_games/realizability_probe/tables/position_summary.csv" \
  --realizability-candidate-csv "${REPO_ROOT}/outputs/analyses/20260510_realizability_probe_100_games/realizability_probe/tables/candidate_feature_table.csv" \
  --split-games \
  --copy-board-assets
