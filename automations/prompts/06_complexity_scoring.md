# Step 06 Prompt

## Goal

Expand the probability tree for 3 plies and compute the provisional complexity score.

## Check

- only moves with probability `>= 0.10` are counted
- tree depth is exactly 3 plies unless a branch terminates early
- the high-complexity threshold is applied consistently

## Expected outputs

- full score table path
- high-complexity subset path
- quick summary of score distribution
