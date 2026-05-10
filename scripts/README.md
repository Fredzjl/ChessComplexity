# Scripts

Canonical entrypoints are now grouped by responsibility:

- `pipeline/`
  - download, parse, filter, inference, scoring
- `review/`
  - board previews, review bundles, review website generation
- `setup/`
  - local environment and model verification

Compatibility wrappers remain at `scripts/*.py` so older commands still work.

The actual experiment logic should stay in `src/`.
