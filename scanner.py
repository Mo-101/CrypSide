#!/usr/bin/env python3
"""
Idim Ikang local observer scanner.
Baseline-aligned observer for live market scanning on existing WSL2 sovereign stack.

Important:
- This ports the locked baseline *behavioral intent* into a self-contained live observer.
- If Claude's exact validator scoring implementation differs, replace only the score_* functions below.
"""

from __future__ import annotations
import json
import math
import os
import signal
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", "https://api.binance.com")
SCAN_INTERVAL_SECONDS = int(os.environ.get("SCAN_INTERVAL_SECONDS", "60"))
LOOKBACK_15M = int(os.environ.get("LOOKBACK_15M", "500"))
LOOKBACK_4H = int(os.environ.get("LOOKBACK_4H", "300"))

LOGIC_VERSION = os.environ.get("LOGIC_VERSION", "v1.0-baseline-observer")
CONFIG_VERSION = os.environ.get("CONFIG_VERSION", "v1.0-baseline-observer")

# Historical observed out-of-sample baseline constants
MIN_SIGNAL_SCORE = 45
COOLDOWN_BARS = 32
BLOCK_STRONG_UPTREND = True
ATR_SL_MULTIPLIER = 1.0
ATR_TP_MULTIPLIER = 3.0

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

_STOP = False
_LAST_SIGNAL: Optional[dict] = None
_START_TS = time.time()
_LAST_SCAN_TS: Optional[float] = None
_LAST_SCAN_GAP_SECONDS: Optional[float] = None


def handle_stop(signum, frame):
    global _STOP
    _STOP = True

signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def db_conn():
    return psycopg2.connect(DATABASE_URL)


def log_event(level: str, component: str, event: str, details: dict):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO system_logs(level, component, event, details)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (level, component, event, json.dumps(details)),
        )
        conn.commit()


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    Bot(token=TELEGRAM_BOT_TOKEN).send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    url = f"{BINANCE_BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ]
    df = pd.DataFrame(data, columns=cols)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    # finalized candles only
    now_ms = int(time.time() * 1000)
    df = df[df["close_time"].astype("int64") // 10**6 <= now_ms].copy()
    return df.reset_index(drop=True)


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd_hist(series: pd.Series) -> pd.Series:
    ema12 = ema(series, 12)
    ema26 = ema(series, 26)
    macd = ema12 - ema26
    signal = ema(macd, 9)
    return macd - signal


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["rsi14"] = rsi(out["close"], 14)
    out["macd_hist"] = macd_hist(out["close"])
    out["atr14"] = atr(out, 14)
    out["volume_sma20"] = out["volume"].rolling(20).mean()
    return out


def classify_regime(df4h: pd.DataFrame) -> str:
    x = df4h.copy()
    x["ema20"] = ema(x["close"], 20)
    x["ema50"] = ema(x["close"], 50)
    x["atr14"] = atr(x, 14)
    latest = x.iloc[-1]
    atr_pct = latest["atr14"] / latest["close"] if latest["close"] else 0
    ema_spread = (latest["ema20"] - latest["ema50"]) / latest["close"] if latest["close"] else 0
    if atr_pct > 0.02 and ema_spread > 0.01:
        return "STRONG_UPTREND"
    if ema_spread > 0.003:
        return "UPTREND"
    if atr_pct > 0.02 and ema_spread < -0.01:
        return "STRONG_DOWNTREND"
    if ema_spread < -0.003:
        return "DOWNTREND"
    return "RANGING"


def cooldown_active(conn, pair: str, latest_ts: datetime) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts FROM signals
            WHERE pair = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (pair,),
        )
        row = cur.fetchone()
        if not row:
            return False
        last_ts = row[0]
        return (latest_ts - last_ts).total_seconds() < COOLDOWN_BARS * 15 * 60


def score_long_signal(latest: pd.Series, regime: str) -> Tuple[float, Dict]:
    reasons_pass, reasons_fail = [], []
    score = 0.0

    ema_aligned = latest["ema20"] > latest["ema50"]
    if ema_aligned:
        score += 20
        reasons_pass.append("EMA20 > EMA50 (trend aligned)")
    else:
        reasons_fail.append("EMA20 <= EMA50")

    if latest["close"] > latest["ema20"]:
        score += 10
        reasons_pass.append("Price above EMA20")
    else:
        reasons_fail.append("Price <= EMA20")

    rsi_val = latest["rsi14"]
    if 30 <= rsi_val <= 65:
        score += 15
        reasons_pass.append(f"RSI {rsi_val:.1f} in bull zone")
    else:
        reasons_fail.append(f"RSI {rsi_val:.1f} outside bull zone")

    if latest["macd_hist"] > 0:
        score += 15
        reasons_pass.append("MACD histogram positive")
    else:
        reasons_fail.append("MACD histogram <= 0")

    if regime == "RANGING":
        score += 0
    elif regime == "UPTREND":
        score += 10
    elif regime == "STRONG_UPTREND":
        score += 0 if BLOCK_STRONG_UPTREND else 15
    elif regime == "DOWNTREND":
        score += 5
    elif regime == "STRONG_DOWNTREND":
        score += 0
    reasons_pass.append(f"Regime: {regime}")

    vol_ratio = latest["volume"] / latest["volume_sma20"] if latest["volume_sma20"] and not np.isnan(latest["volume_sma20"]) else 0
    if vol_ratio >= 1.1:
        score += 15
        reasons_pass.append(f"Volume ratio {vol_ratio:.2f} (confirmed)")
    else:
        reasons_fail.append(f"Volume ratio {vol_ratio:.2f} below 1.1")

    return score, {"reasons_pass": reasons_pass, "reasons_fail": reasons_fail, "volume_ratio": vol_ratio}


def score_short_signal(latest: pd.Series, regime: str) -> Tuple[float, Dict]:
    reasons_pass, reasons_fail = [], []
    score = 0.0

    ema_aligned = latest["ema20"] < latest["ema50"]
    if ema_aligned:
        score += 20
        reasons_pass.append("EMA20 < EMA50 (trend aligned)")
    else:
        reasons_fail.append("EMA20 >= EMA50")

    if latest["close"] < latest["ema20"]:
        score += 10
        reasons_pass.append("Price below EMA20")
    else:
        reasons_fail.append("Price >= EMA20")

    rsi_val = latest["rsi14"]
    if 35 <= rsi_val <= 70:
        score += 15
        reasons_pass.append(f"RSI {rsi_val:.1f} in bear zone")
    else:
        reasons_fail.append(f"RSI {rsi_val:.1f} outside bear zone")

    if latest["macd_hist"] < 0:
        score += 15
        reasons_pass.append("MACD histogram negative")
    else:
        reasons_fail.append("MACD histogram >= 0")

    if regime == "RANGING":
        score += 0
    elif regime == "DOWNTREND":
        score += 10
    elif regime == "STRONG_DOWNTREND":
        score += 15
    elif regime == "UPTREND":
        score += 5
    elif regime == "STRONG_UPTREND":
        score += 0 if BLOCK_STRONG_UPTREND else 0
    reasons_pass.append(f"Regime: {regime}")

    vol_ratio = latest["volume"] / latest["volume_sma20"] if latest["volume_sma20"] and not np.isnan(latest["volume_sma20"]) else 0
    if vol_ratio >= 1.1:
        score += 15
        reasons_pass.append(f"Volume ratio {vol_ratio:.2f} (confirmed)")
    else:
        reasons_fail.append(f"Volume ratio {vol_ratio:.2f} below 1.1")

    return score, {"reasons_pass": reasons_pass, "reasons_fail": reasons_fail, "volume_ratio": vol_ratio}


def build_signal(pair: str, side: str, latest: pd.Series, regime: str, score: float, trace: Dict) -> dict:
    atr_val = float(latest["atr14"])
    entry = float(latest["close"])
    if side == "LONG":
        stop = entry - ATR_SL_MULTIPLIER * atr_val
        tp = entry + ATR_TP_MULTIPLIER * atr_val
    else:
        stop = entry + ATR_SL_MULTIPLIER * atr_val
        tp = entry - ATR_TP_MULTIPLIER * atr_val
    return {
        "signal_id": str(uuid.uuid4()),
        "pair": pair,
        "ts": latest["close_time"].to_pydatetime(),
        "side": side,
        "entry": entry,
        "stop_loss": stop,
        "take_profit": tp,
        "score": score,
        "regime": regime,
        "reason_trace": trace,
        "logic_version": LOGIC_VERSION,
        "config_version": CONFIG_VERSION,
    }


def insert_signal(conn, sig: dict):
    global _LAST_SIGNAL
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO signals (
                signal_id, pair, ts, side, entry, stop_loss, take_profit,
                score, regime, reason_trace, logic_version, config_version
            )
            VALUES (
                %(signal_id)s, %(pair)s, %(ts)s, %(side)s, %(entry)s, %(stop_loss)s, %(take_profit)s,
                %(score)s, %(regime)s, %(reason_trace)s::jsonb, %(logic_version)s, %(config_version)s
            )
            ON CONFLICT (signal_id) DO NOTHING
            """,
            {**sig, "reason_trace": json.dumps(sig["reason_trace"])},
        )
        conn.commit()
    _LAST_SIGNAL = {**sig, "ts": sig["ts"].isoformat()}
    send_telegram(
        f"Idim Ikang signal\n"
        f"{sig['pair']} {sig['side']}\n"
        f"Score: {sig['score']}\n"
        f"Regime: {sig['regime']}\n"
        f"Entry: {sig['entry']:.4f}\n"
        f"SL: {sig['stop_loss']:.4f}\n"
        f"TP: {sig['take_profit']:.4f}"
    )


from g4_whitelist_gate import WhitelistGate

WHITELIST_GATE = WhitelistGate(Path(__file__).parent / "whitelist.json")

def g4_passes(policy: str, regime: str, side: str) -> tuple[bool, dict | None]:
    allowed = WHITELIST_GATE.is_allowed(policy=policy, regime=regime, side=side)
    meta = WHITELIST_GATE.get_meta(policy=policy, regime=regime, side=side)
    return allowed, meta

def scan_once():
    global _LAST_SCAN_TS, _LAST_SCAN_GAP_SECONDS
    started = time.time()
    if _LAST_SCAN_TS is not None:
        _LAST_SCAN_GAP_SECONDS = started - _LAST_SCAN_TS
        if _LAST_SCAN_GAP_SECONDS > SCAN_INTERVAL_SECONDS * 2.5:
            log_event("WARN", "scanner", "scan_gap_detected", {"gap_seconds": _LAST_SCAN_GAP_SECONDS})
    _LAST_SCAN_TS = started

    with db_conn() as conn:
        for pair in PAIRS:
            df15 = add_indicators(fetch_klines(pair, "15m", LOOKBACK_15M))
            df4 = fetch_klines(pair, "4h", LOOKBACK_4H)
            regime = classify_regime(df4)

            latest = df15.iloc[-1]
            if any(np.isnan(latest.get(k, np.nan)) for k in ["ema20", "ema50", "rsi14", "macd_hist", "atr14", "volume_sma20"]):
                log_event("INFO", "scanner", "warmup_or_nan_skip", {"pair": pair})
                continue

            if cooldown_active(conn, pair, latest["close_time"].to_pydatetime()):
                continue

            long_score, long_trace = score_long_signal(latest, regime)
            short_score, short_trace = score_short_signal(latest, regime)

            if long_score >= MIN_SIGNAL_SCORE and long_score >= short_score:
                allowed, pocket_meta = g4_passes(policy=LOGIC_VERSION, regime=regime, side="LONG")
                if not allowed:
                    log_event("INFO", "scanner", "g4_whitelist_block", {
                        "policy": LOGIC_VERSION, "regime": regime, "side": "LONG", "whitelist_size": WHITELIST_GATE.size
                    })
                else:
                    long_trace["g4_whitelist"] = pocket_meta
                    sig = build_signal(pair, "LONG", latest, regime, long_score, long_trace)
                    insert_signal(conn, sig)
                    log_event("INFO", "scanner", "signal_logged", {"pair": pair, "side": "LONG", "score": long_score, "regime": regime})

            elif short_score >= MIN_SIGNAL_SCORE and short_score > long_score:
                allowed, pocket_meta = g4_passes(policy=LOGIC_VERSION, regime=regime, side="SHORT")
                if not allowed:
                    log_event("INFO", "scanner", "g4_whitelist_block", {
                        "policy": LOGIC_VERSION, "regime": regime, "side": "SHORT", "whitelist_size": WHITELIST_GATE.size
                    })
                else:
                    short_trace["g4_whitelist"] = pocket_meta
                    sig = build_signal(pair, "SHORT", latest, regime, short_score, short_trace)
                    insert_signal(conn, sig)
                    log_event("INFO", "scanner", "signal_logged", {"pair": pair, "side": "SHORT", "score": short_score, "regime": regime})

    log_event("INFO", "scanner", "scan_complete", {"duration_seconds": round(time.time() - started, 3)})


def main():
    log_event("INFO", "scanner", "scanner_start", {"pairs": PAIRS, "logic_version": LOGIC_VERSION, "config_version": CONFIG_VERSION})
    while not _STOP:
        try:
            scan_once()
        except Exception as e:
            log_event("ERROR", "scanner", "scan_error", {"error": str(e)})
        time.sleep(SCAN_INTERVAL_SECONDS)
    log_event("INFO", "scanner", "scanner_stop", {"uptime_seconds": round(time.time() - _START_TS, 1)})


if __name__ == "__main__":
    main()
