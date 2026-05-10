# MVP Spec

## Goal

Run one small but complete experiment that can be inspected manually.

## Data slice

- Source: 10 Lichess standard games
- Unit of analysis: candidate positions after each ply within fullmoves 10 to 30 inclusive
- Skip a position if either side has fewer than 8 remaining pieces, counting the king

## Maia-2 requirement

- Install Maia-2 locally
- Verify at least one successful policy inference before running the full experiment
- Save both the raw model output and a normalized top-k view

## Provisional complexity score

For each eligible position:

1. Query Maia-2 for the current move distribution
2. Keep moves with probability `>= 0.10`
3. Expand every qualifying move for up to 3 plies
4. At every expanded node, again keep moves with probability `>= 0.10`
5. Define:

`complexity_score = total number of qualifying move edges in the 3-ply tree`

## Provisional classification threshold

- `high_complexity = complexity_score >= 10`

Rationale:

- The threshold is deliberately simple
- It should surface positions with multiple plausible human continuations
- It is easy to audit against saved probability distributions

## Required saved artifacts

- downloaded PGN sample
- parsed game table
- parsed position table
- filtered middlegame position table
- per-position Maia-2 probability distributions
- per-position complexity scores
- PNG images for flagged high-complexity positions
- a run summary with counts and file paths
