# CSV Column Contract — trades.csv

## Required
- `trade_id` — unique string
- `policy` — string (e.g. phase2_v1, phase2_data_burst_v1, phase2_rr_repair_v1, unknown)
- `regime` — one of: STRONG_UPTREND, UPTREND, RANGING, DOWNTREND, STRONG_DOWNTREND
- `side` — LONG | SHORT
- `outcome` — WIN | LOSS | UNRESOLVED (empty -> UNRESOLVED)
- `r_multiple` — signed float; required if outcome in {WIN,LOSS}
- `emitted_at` — ISO 8601 timestamp

## Recommended
- resolved_at, symbol, family, hour_utc, sl_x, tp_x, sprint_tag

## Optional / preserved
- score, legacy_score, prob_score, pwin, risk_scale, execution_source, btc_regime

## Pocket identity (current)
`policy | regime | side`

Hour/family/symbol NOT part of identity per sprint patch. Can be added to the identity key
once per-hour/per-family posteriors pass the same MIN_N=5, P≥0.75 bar.
