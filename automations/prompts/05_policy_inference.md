# Step 05 Prompt

## Goal

Run Maia-2 policy inference for every eligible position and save both raw and flattened outputs.

## Check

- raw model outputs are stored without truncating key fields
- a flattened top-k table exists for quick inspection
- failed positions are logged explicitly

## Expected outputs

- raw policy snapshot path
- flattened policy table path
- counts of successful and failed inferences
