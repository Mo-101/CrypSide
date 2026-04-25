#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import time
from datetime import timezone

import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", "https://api.binance.com")
LOOP_SECONDS = 900


def db_conn():
    return psycopg2.connect(DATABASE_URL)


def log_event(level: str, component: str, event: str, details: dict):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO system_logs(level, component, event, details) VALUES (%s,%s,%s,%s::jsonb)",
            (level, component, event, json.dumps(details)),
        )
        conn.commit()


def fetch_since(symbol: str, start_ms: int, interval: str = "15m", limit: int = 1000):
    url = f"{BINANCE_BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "startTime": start_ms, "limit": limit}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ]
    df = pd.DataFrame(r.json(), columns=cols)
    if df.empty:
        return df
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype(float)
    return df


def resolve_signal(sig: dict):
    ts_ms = int(sig["ts"].timestamp() * 1000)
    df = fetch_since(sig["pair"], ts_ms)
    if df.empty:
        return None, None

    side = sig["side"]
    sl = float(sig["stop_loss"])
    tp = float(sig["take_profit"])
    for _, row in df.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        if side == "LONG":
            if low <= sl:
                return "LOSS", -1.0
            if high >= tp:
                return "WIN", 3.0
        else:
            if high >= sl:
                return "LOSS", -1.0
            if low <= tp:
                return "WIN", 3.0
    return None, None


def run_once():
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, signal_id, pair, ts, side, stop_loss, take_profit
            FROM signals
            WHERE outcome IS NULL
            ORDER BY ts ASC
            LIMIT 500
            """
        )
        rows = cur.fetchall()

    updates = 0
    for row in rows:
        outcome, r_mult = resolve_signal(row)
        if outcome is None:
            continue
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE signals
                SET outcome = %s, r_multiple = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (outcome, r_mult, row["id"]),
            )
            conn.commit()
        updates += 1

    log_event("INFO", "outcome_tracker", "tracker_run_complete", {"checked": len(rows), "updated": updates})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    if args.loop:
        while True:
            try:
                run_once()
            except Exception as e:
                log_event("ERROR", "outcome_tracker", "tracker_error", {"error": str(e)})
            time.sleep(LOOP_SECONDS)
    else:
        run_once()


if __name__ == "__main__":
    main()
