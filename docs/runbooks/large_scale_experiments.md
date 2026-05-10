# Large-Scale Experiments

## When the dataset grows

Once experiments move beyond the current small prototype, use these conventions:

- Keep one config file per experiment family under `configs/experiments/`
- Use stable run ids such as `YYYYMMDD_<experiment_name>_<batch_tag>`
- Save intermediate machine outputs in `outputs/runs/<run_id>/`
- Save derived analysis tables in `outputs/analyses/<analysis_id>/`
- Export review-focused subsets to `outputs/reviews/<review_id>/`
- Build browser deliverables into `outputs/sites/<site_id>/`

## Suggested workflow

1. Download or register the raw dataset in `data/raw/`
2. Parse and filter into structured tables
3. Run model inference and engine annotations
4. Score and flag positions
5. Export a review bundle
6. Build a review website from the review bundle

## Naming guidance

- `run_id`
  - computation-oriented, may include batch or seed info
- `review_id`
  - analyst-oriented, may include threshold or shortlist version
- `site_id`
  - presentation-oriented, may include audience or date
