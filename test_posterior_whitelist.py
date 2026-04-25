"""
test_posterior_whitelist.py
pytest-compatible tests. Run: pytest test_posterior_whitelist.py -v
"""
from posterior_whitelist import (
    aggregate_pockets, select_whitelist, beta_survival,
    MIN_N, SUCCESS_WR_THRESHOLD, MIN_POSTERIOR_PASS_PROB,
)


def test_posterior_filter_basic_winner_and_loser():
    rows = [
        # Winner: 4W / 1L at (p1, UPTREND, LONG) -> observed 80%, should qualify
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "LOSS"},
        # Loser: 1W / 4L at (p2, RANGING, SHORT) -> observed 20%, should not qualify
        {"policy": "p2", "regime": "RANGING", "side": "SHORT", "outcome": "LOSS"},
        {"policy": "p2", "regime": "RANGING", "side": "SHORT", "outcome": "LOSS"},
        {"policy": "p2", "regime": "RANGING", "side": "SHORT", "outcome": "LOSS"},
        {"policy": "p2", "regime": "RANGING", "side": "SHORT", "outcome": "LOSS"},
        {"policy": "p2", "regime": "RANGING", "side": "SHORT", "outcome": "WIN"},
    ]
    pockets = aggregate_pockets(rows)
    selected = select_whitelist(pockets)
    ids = {p.pocket_id for p in selected}
    assert "p1|UPTREND|LONG" in ids
    assert "p2|RANGING|SHORT" not in ids


def test_min_n_rejects_small_pockets():
    rows = [
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
    ]
    pockets = aggregate_pockets(rows)
    assert len(pockets) == 1 and pockets[0].n == 4
    selected = select_whitelist(pockets)
    assert len(selected) == 0, "n=4 must be rejected by MIN_N=5"


def test_beta_survival_known_values():
    # P(X >= 0.5) for Beta(1,1) uniform = 0.5
    assert abs(beta_survival(1.0, 1.0, 0.5) - 0.5) < 0.01
    # P(X >= 0.0) = 1.0
    assert beta_survival(2.0, 3.0, 0.0) == 1.0
    # P(X >= 1.0) = 0.0
    assert beta_survival(2.0, 3.0, 1.0) == 0.0


def test_invalid_rows_skipped():
    rows = [
        {"policy": "p1", "regime": "BAD_REGIME", "side": "LONG", "outcome": "WIN"},
        {"policy": "",  "regime": "UPTREND", "side": "LONG", "outcome": "WIN"},
        {"policy": "p1", "regime": "UPTREND", "side": "DIAGONAL", "outcome": "WIN"},
    ]
    pockets = aggregate_pockets(rows)
    assert len(pockets) == 0


def test_unresolved_counts_toward_n_but_not_posterior():
    rows = [{"policy": "p1", "regime": "UPTREND", "side": "LONG", "outcome": "UNRESOLVED"}] * 10
    pockets = aggregate_pockets(rows)
    assert pockets[0].n == 10
    assert pockets[0].wins == 0 and pockets[0].losses == 0 and pockets[0].unresolved == 10
