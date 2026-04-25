# Scanner G4 Integration Patch

Replace the current rolling-50 qualification in the scanner with whitelist-only gating.

## Location
Scanner evaluation path (the block currently at lines ~3227-3254 where G4 is wired).

## Remove (old logic)
```python
# old pseudo-logic — rolling-50 qualification
if pocket_n_in_rolling_50 < 10:
    reject("G4 pocket not qualified")
```

## Add (new logic)
```python
from g4_whitelist_gate import WhitelistGate

WHITELIST_GATE = WhitelistGate("/home/idona/.../whitelist.json")

def g4_passes(policy: str, regime: str, side: str) -> tuple[bool, dict | None]:
    allowed = WHITELIST_GATE.is_allowed(policy=policy, regime=regime, side=side)
    meta = WHITELIST_GATE.get_meta(policy=policy, regime=regime, side=side)
    return allowed, meta


# inside signal evaluation, after G1/G2/G3:
allowed, pocket_meta = g4_passes(
    policy=current_policy,
    regime=current_regime,
    side=current_side,
)

if not allowed:
    # Log rejection — matches rejection gate taxonomy in the review report
    reject_reason = "g4_whitelist_block"
    log_rejection(reject_reason, {
        "policy": current_policy,
        "regime": current_regime,
        "side": current_side,
        "whitelist_size": WHITELIST_GATE.size,
    })
    return None

# Enrich reason trace on passage
reason_trace["g4_whitelist"] = pocket_meta
emitted.append(signal)
```

## Operational notes

1. **Pocket identity is (policy, regime, side).** No hour, no family, no symbol — per sprint patch.
2. **The whitelist file is the single source of truth.** To update it, run `posterior_whitelist.py` against updated trades.csv and call `WHITELIST_GATE.reload()` (or restart the scanner).
3. **An empty whitelist is a total block.** This is by design — if no pocket qualifies, no signals emit.
4. **Covenant statement for the audit trail:**
   > G4 emits only when the observed pocket has cumulative n≥5 AND posterior P(true_WR≥0.50)≥0.75. Rolling-window qualification is abandoned as mathematically unreachable at current emission rates.

## Rollback
`git checkout main -- scanner.py` reverts to the pre-whitelist scanner. Whitelist.json can remain on disk harmlessly.
