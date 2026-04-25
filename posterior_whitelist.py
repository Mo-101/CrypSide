"""
posterior_whitelist.py
Covenant-grade posterior whitelist generator for G4 gating.

Generates whitelist.json from a raw trades CSV.
Pocket identity: (policy, regime, side).
Selection: cumulative-N, Beta posterior filter.

Run:
    python posterior_whitelist.py --trades-csv trades.csv --whitelist-json whitelist.json --report-json report.json
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# -------- CONFIG --------
MIN_N = 5
SUCCESS_WR_THRESHOLD = 0.50
MIN_POSTERIOR_PASS_PROB = 0.75

PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0

VALID_REGIMES = {"STRONG_UPTREND", "UPTREND", "RANGING", "DOWNTREND", "STRONG_DOWNTREND"}
VALID_SIDES = {"LONG", "SHORT"}


@dataclass
class PocketStats:
    policy: str
    regime: str
    side: str
    n: int
    wins: int
    losses: int
    unresolved: int
    observed_wr: float
    posterior_alpha: float
    posterior_beta: float
    posterior_mean_wr: float
    p_true_wr_ge_threshold: float

    @property
    def pocket_id(self) -> str:
        return f"{self.policy}|{self.regime}|{self.side}"


def load_trades_csv(path: str | Path) -> List[dict]:
    path = Path(path)
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def normalize_outcome(value: str | None) -> str:
    if value is None:
        return "UNRESOLVED"
    v = value.strip().upper()
    return v if v in {"WIN", "LOSS", "UNRESOLVED"} else "UNRESOLVED"


def beta_survival(alpha: float, beta: float, threshold: float, steps: int = 20000) -> float:
    """P(X >= threshold) for X ~ Beta(alpha, beta). Midpoint rule. No scipy."""
    if threshold <= 0.0:
        return 1.0
    if threshold >= 1.0:
        return 0.0

    log_norm = -(math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta))

    lo, hi = threshold, 1.0
    width = (hi - lo) / steps
    total = 0.0
    for i in range(steps):
        x = lo + (i + 0.5) * width
        if x <= 0.0 or x >= 1.0:
            continue
        log_pdf = (alpha - 1.0) * math.log(x) + (beta - 1.0) * math.log(1.0 - x) + log_norm
        total += math.exp(log_pdf) * width
    return max(0.0, min(1.0, total))


def aggregate_pockets(rows: Iterable[dict]) -> List[PocketStats]:
    grouped: Dict[Tuple[str, str, str], Dict] = {}

    for row in rows:
        policy = (row.get("policy") or "").strip()
        regime = (row.get("regime") or "").strip()
        side = (row.get("side") or "").strip().upper()
        outcome = normalize_outcome(row.get("outcome"))

        if not policy or regime not in VALID_REGIMES or side not in VALID_SIDES:
            continue

        key = (policy, regime, side)
        if key not in grouped:
            grouped[key] = {
                "policy": policy, "regime": regime, "side": side,
                "n": 0, "wins": 0, "losses": 0, "unresolved": 0,
            }

        grouped[key]["n"] += 1
        if outcome == "WIN":
            grouped[key]["wins"] += 1
        elif outcome == "LOSS":
            grouped[key]["losses"] += 1
        else:
            grouped[key]["unresolved"] += 1

    pockets: List[PocketStats] = []
    for g in grouped.values():
        wins, losses, unresolved = int(g["wins"]), int(g["losses"]), int(g["unresolved"])
        resolved = wins + losses
        observed_wr = wins / resolved if resolved > 0 else 0.0
        alpha = PRIOR_ALPHA + wins
        beta = PRIOR_BETA + losses
        posterior_mean = alpha / (alpha + beta)
        p_pass = beta_survival(alpha, beta, SUCCESS_WR_THRESHOLD)

        pockets.append(PocketStats(
            policy=g["policy"], regime=g["regime"], side=g["side"],
            n=int(g["n"]), wins=wins, losses=losses, unresolved=unresolved,
            observed_wr=observed_wr,
            posterior_alpha=alpha, posterior_beta=beta,
            posterior_mean_wr=posterior_mean,
            p_true_wr_ge_threshold=p_pass,
        ))

    pockets.sort(
        key=lambda p: (p.p_true_wr_ge_threshold, p.posterior_mean_wr, p.n),
        reverse=True,
    )
    return pockets


def select_whitelist(pockets: Iterable[PocketStats]) -> List[PocketStats]:
    return [p for p in pockets
            if p.n >= MIN_N and p.p_true_wr_ge_threshold >= MIN_POSTERIOR_PASS_PROB]


def write_whitelist_json(pockets: Iterable[PocketStats], output_path: str | Path,
                         source_meta: dict | None = None) -> None:
    output_path = Path(output_path)
    payload = {
        "schema_version": "1.0",
        "selection_method": "cumulative_posterior_filter",
        "min_n": MIN_N,
        "success_wr_threshold": SUCCESS_WR_THRESHOLD,
        "min_posterior_pass_prob": MIN_POSTERIOR_PASS_PROB,
        "prior": {"alpha": PRIOR_ALPHA, "beta": PRIOR_BETA},
        "generated_from": source_meta or {},
        "pockets": [
            {
                "pocket_id": p.pocket_id,
                "policy": p.policy, "regime": p.regime, "side": p.side,
                "n": p.n, "wins": p.wins, "losses": p.losses, "unresolved": p.unresolved,
                "observed_wr": round(p.observed_wr, 6),
                "posterior_mean_wr": round(p.posterior_mean_wr, 6),
                "p_true_wr_ge_threshold": round(p.p_true_wr_ge_threshold, 6),
            }
            for p in pockets
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(trades_csv: str, whitelist_json: str, report_json: str | None = None) -> None:
    rows = load_trades_csv(trades_csv)
    pockets = aggregate_pockets(rows)
    selected = select_whitelist(pockets)

    source_meta = {
        "source": str(Path(trades_csv).name),
        "total_rows": len(rows),
        "total_pockets_found": len(pockets),
        "pocket_identity": "policy|regime|side",
    }
    write_whitelist_json(selected, whitelist_json, source_meta=source_meta)

    if report_json:
        report = {
            "thresholds": {
                "MIN_N": MIN_N,
                "SUCCESS_WR_THRESHOLD": SUCCESS_WR_THRESHOLD,
                "MIN_POSTERIOR_PASS_PROB": MIN_POSTERIOR_PASS_PROB,
                "PRIOR_ALPHA": PRIOR_ALPHA,
                "PRIOR_BETA": PRIOR_BETA,
            },
            "source": source_meta,
            "all_pockets": [asdict(p) for p in pockets],
            "selected_pockets": [asdict(p) for p in selected],
        }
        Path(report_json).write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Loaded trades: {len(rows)}")
    print(f"All pockets (policy|regime|side): {len(pockets)}")
    print(f"Qualifying pockets: {len(selected)}")
    for p in selected:
        print(
            f"  {p.pocket_id} | n={p.n} | W/L={p.wins}/{p.losses} | "
            f"obs_wr={p.observed_wr:.3f} | post_mean={p.posterior_mean_wr:.3f} | "
            f"p(true_wr>={SUCCESS_WR_THRESHOLD:.2f})={p.p_true_wr_ge_threshold:.3f}"
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate posterior-filtered whitelist from raw trades CSV.")
    parser.add_argument("--trades-csv", required=True)
    parser.add_argument("--whitelist-json", required=True)
    parser.add_argument("--report-json", required=False)
    args = parser.parse_args()
    main(args.trades_csv, args.whitelist_json, args.report_json)
