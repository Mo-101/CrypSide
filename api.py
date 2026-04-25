#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
PM2_SCANNER_NAME = os.environ.get("PM2_SCANNER_NAME", "idim-scanner")
START_TS = time.time()

app = FastAPI(title="Idim Ikang API", version="v1")


def db_conn():
    return psycopg2.connect(DATABASE_URL)


@app.get("/status")
def status():
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT ts, pair, side, score, regime FROM signals ORDER BY ts DESC LIMIT 1")
        last_signal = cur.fetchone()
        cur.execute("SELECT ts, level, event, details FROM system_logs ORDER BY ts DESC LIMIT 1")
        last_log = cur.fetchone()
    return {
        "service": "idim-api",
        "uptime_seconds": round(time.time() - START_TS, 1),
        "scanner_pm2_name": PM2_SCANNER_NAME,
        "last_signal": last_signal,
        "last_log": last_log,
    }


@app.get("/signals")
def signals():
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT signal_id, pair, ts, side, entry, stop_loss, take_profit, score, regime,
                   reason_trace, logic_version, config_version, outcome, r_multiple
            FROM signals
            ORDER BY ts DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()
    return {"count": len(rows), "signals": rows}


@app.post("/kill")
def kill():
    try:
        subprocess.run(["pm2", "stop", PM2_SCANNER_NAME], check=True, capture_output=True, text=True)
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO system_logs(level, component, event, details) VALUES (%s,%s,%s,%s::jsonb)",
                ("WARN", "api", "kill_switch_invoked", json.dumps({"pm2_process": PM2_SCANNER_NAME}))
            )
            conn.commit()
        return {"status": "stopped", "scanner": PM2_SCANNER_NAME}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
