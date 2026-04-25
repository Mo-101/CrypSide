#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import signal
import subprocess
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query

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


@app.get("/history")
def history(
    limit: int = 100, 
    pair: Optional[str] = None, 
    side: Optional[str] = None, 
    outcome: Optional[str] = None,
    from_date: Optional[str] = None
):
    query = """
        SELECT signal_id, pair, ts, side, entry, stop_loss, take_profit, score, regime,
               logic_version, config_version, outcome, r_multiple, source, created_at, updated_at
        FROM signals
        WHERE 1=1
    """
    params = []
    
    if pair:
        query += " AND pair = %s"
        params.append(pair)
    if side:
        query += " AND side = %s"
        params.append(side)
    if outcome:
        query += " AND outcome = %s"
        params.append(outcome)
    if from_date:
        query += " AND ts >= %s"
        params.append(from_date)
        
    query += " ORDER BY ts DESC LIMIT %s"
    params.append(limit)
    
    with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        
    return {"count": len(rows), "history": rows}


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


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # We need to handle disconnected clients during broadcast
        import uuid
        import decimal
        
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                if isinstance(obj, decimal.Decimal):
                    return float(obj)
                return super().default(obj)
                
        message_str = json.dumps(message, cls=CustomJSONEncoder)
        
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_str)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We just keep the connection open and wait for the background task to push data
            # Or we can accept ping/pong messages here
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def _poll_database_for_updates():
    last_signal_id = None
    last_log_id = None
    
    # Initialize the IDs to not broadcast old data on server start
    try:
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM signals ORDER BY id DESC LIMIT 1")
            res = cur.fetchone()
            if res: last_signal_id = res[0]
            
            cur.execute("SELECT id FROM system_logs ORDER BY id DESC LIMIT 1")
            res = cur.fetchone()
            if res: last_log_id = res[0]
    except Exception as e:
        print(f"Error initializing poller: {e}")
        
    while True:
        await asyncio.sleep(2.0)
        if not manager.active_connections:
            continue
            
        try:
            with db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Check for new signals
                sig_query = "SELECT * FROM signals"
                if last_signal_id is not None:
                    sig_query += f" WHERE id > {last_signal_id}"
                sig_query += " ORDER BY id ASC"
                
                cur.execute(sig_query)
                signals = cur.fetchall()
                for sig in signals:
                    last_signal_id = max(last_signal_id or 0, sig['id'])
                    await manager.broadcast({"type": "new_signal", "data": dict(sig)})
                    
                # Check for new logs
                log_query = "SELECT * FROM system_logs"
                if last_log_id is not None:
                    log_query += f" WHERE id > {last_log_id}"
                log_query += " ORDER BY id ASC"
                
                cur.execute(log_query)
                logs = cur.fetchall()
                for log in logs:
                    last_log_id = max(last_log_id or 0, log['id'])
                    await manager.broadcast({"type": "new_log", "data": dict(log)})
                    
        except Exception as e:
             print(f"Polling error: {e}")
             await asyncio.sleep(5.0)

@app.on_event("startup")
async def startup_event():
    # Start the polling background task
    asyncio.create_task(_poll_database_for_updates())