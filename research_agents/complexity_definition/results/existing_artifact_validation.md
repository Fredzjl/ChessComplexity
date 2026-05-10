# Existing Artifact Validation Summary

## Scope

- Source bundle: `/Users/jialinzhang/Documents/Chess/Complexity_Idea/chess-complexity-full-test/outputs/sites/20260509_balanced_100_games/site/data/site_bundle.json`
- Positions in bundle: `3279`
- High-complexity positions: `2679`
- Non-high-complexity positions: `600`

## Verified Results

### 1. Actual human-move rank is worse in complex positions

- Maia mean rank: `2.9527` in high-complexity vs `2.2759` in non-high-complexity.
- Stockfish mean rank: `4.4904` in high-complexity vs `2.8818` in non-high-complexity.
- Maia hit@1: `0.4524` vs `0.6467`.
- Stockfish hit@1: `0.3124` vs `0.5667`.

### 2. Stockfish changes its mind frequently across time budgets on complex positions

- Complex positions with time-budget traces: `1800`.
- Mean best-move switch count across 6 budgets: `1.5561`.
- Share with at least one best-move switch: `0.65`.
- Share with at least two switches: `0.4722`.
- Correlation between complexity score and switch count: `0.0831`.
- Correlation between complexity score and best-score range: `-0.0553`.

### 3. Strong Stockfish recommendations that Maia dislikes do exist

- Strong-engine positions overall (`Stockfish >= +3.00`): `671`.
- Maia-reluctant among those: `195` (`0.2906`).
- High-complexity flagged rate within strong-engine positions: `0.3107`.
- Non-high-complexity flagged rate within strong-engine positions: `0.2143`.
- When flagged, humans still played the engine-best move only `0.0615` of the time.

## Caveats

- Stockfish actual-move ranks in the bundle are top-20 ranks, not full legal-move ranks.
- Time-budget traces exist only for complex positions selected into the overnight sweep, so this section measures instability within the complex subset rather than complex vs non-complex.
- These results validate phenomena using existing artifacts; they do not yet certify one final complexity definition.

