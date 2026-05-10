# Output Layout

This directory stores generated experiment outputs.

- `runs/`: pipeline-stage outputs tied to one concrete execution
- `reviews/`: analyst-facing review bundles
- `sites/`: generated static websites
- `reports/`: exported summaries, slides, or distribution reports

Pipeline run directories typically contain:

- `metadata/`
- `policy/`
- `complexity/`
- `images/`
- `logs/`

Historical MVP artifacts may still live under `runs/` for compatibility, but future large-scale experiments should prefer:

- `outputs/runs/<run_id>/...` for computation
- `outputs/reviews/<review_id>/...` for human curation
- `outputs/sites/<site_id>/...` for browser-ready delivery
