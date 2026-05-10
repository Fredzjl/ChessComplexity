# Data Layout

- `raw/`: downloaded source files such as PGN samples and large external assets
- `interim/`: parsed or partially filtered data, including engine-ready tables
- `processed/`: final structured tables for scoring, training, or website export
- `manifests/`: small metadata files describing downloaded assets
- `samples/`: hand-picked tiny examples for debugging

For larger experiments, use stable subfolders under `raw/`, `interim/`, and `processed/` per source or workflow family instead of dropping every file into one flat directory.

The first full test should keep all raw inputs reproducible and should never overwrite raw files in place.
