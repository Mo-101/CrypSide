# Mostar Whitelist Pack — Covenant-Grade G4 Gating

Generated: 2026-04-24T07:36:19.135Z

## Contents
- `posterior_whitelist.py` — Beta-posterior whitelist generator (no scipy)
- `g4_whitelist_gate.py` — Runtime gate the scanner imports
- `test_posterior_whitelist.py` — pytest suite
- `scanner_g4_patch.md` — Integration instructions (replaces rolling-50 gate)
- `csv_column_contract.md` — Input schema
- `whitelist.json` — Generated from real trades.csv (391 trades)
- `pocket_posterior_report.json` — All 20 pockets with posteriors

## Config (baked into posterior_whitelist.py)
- MIN_N = 5
- SUCCESS_WR_THRESHOLD = 0.50
- MIN_POSTERIOR_PASS_PROB = 0.75
- Prior = Beta(1, 1)  (uniform)
- Pocket identity = (policy, regime, side)

## What the current whitelist contains
1 pocket:
`phase2_data_burst_v1 | STRONG_UPTREND | LONG` — n=5, 4W/1L, P(true_WR ≥ 0.50) = 0.891

## How to regenerate
```bash
python posterior_whitelist.py \
    --trades-csv /path/to/trades.csv \
    --whitelist-json whitelist.json \
    --report-json pocket_posterior_report.json
```

## Why only one pocket qualifies
See sections 9f, 11 of the review report. The cumulative raw-row WR for every
other pocket falls below the posterior pass bar once sub-window cherry-picking
is removed. This is the overfit Wolfram originally warned against — made explicit.
