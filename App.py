import json
import time
import pandas as pd
import pandas_ta as ta
import streamlit as st
import websocket
import threading

# -----------------------------
# Config
# -----------------------------
ASSETS = [
    {"symbol": "ethusdt", "label": "Ethereum"},
    {"symbol": "solusdt", "label": "Solana"},
    {"symbol": "xrpusdt", "label": "XRP"},
    {"symbol": "zecusdt", "label": "Zcash"},
]

# Global storage for live prices
price_buffers = {a["symbol"]: [] for a in ASSETS}

# -----------------------------
# WebSocket handler
# -----------------------------
def on_message(ws, message):
    data = json.loads(message)
    symbol = data.get("s", "").lower()
    price = float(data.get("p", 0))
    ts = pd.to_datetime(data.get("T"), unit="ms")
    if symbol in price_buffers:
        price_buffers[symbol].append({"time": ts, "close": price})
        # keep only last 500 points
        price_buffers[symbol] = price_buffers[symbol][-500:]

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def run_socket():
    streams = "/".join([f"{a['symbol']}@trade" for a in ASSETS])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    ws = websocket.WebSocketApp(url, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.run_forever()

# Start WebSocket in background thread
threading.Thread(target=run_socket, daemon=True).start()

# -----------------------------
# Indicators
# -----------------------------
def compute_indicators(df: pd.DataFrame):
    if df.empty:
        return df
    df["rsi"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd["MACD_12_26_9"]
    df["macd_signal"] = macd["MACDs_12_26_9"]
    df["macd_hist"] = macd["MACDh_12_26_9"]
    # PSAR placeholder (since we only have close)
    df["psar"] = df["close"].shift(1)
    return df

def confirmation_bundle(df: pd.DataFrame):
    if df.empty:
        return {}
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    rsi = latest["rsi"]

    macd_cross_up = (prev["macd"] < prev["macd_signal"]) and (latest["macd"] > latest["macd_signal"])
    macd_cross_down = (prev["macd"] > prev["macd_signal"])
