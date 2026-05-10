# Step 04 Prompt

## Goal

Parse the 10 games into position-level records and filter to eligible middlegame positions.

## Check

- every position has a stable `position_id`
- fullmove number is recorded
- remaining piece counts are recorded for both sides
- skipped positions have an explicit reason

## Expected outputs

- parsed table path
- filtered table path
- skip-reason summary
