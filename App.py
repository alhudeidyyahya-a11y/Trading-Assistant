import time
import requests
import pandas as pd
import pandas_ta as ta
import streamlit as st

# -----------------------------
# Config
# -----------------------------
ASSETS = [
    {"symbol": "ETHUSDT", "label": "Ethereum"},
    {"symbol": "SOLUSDT", "label": "Solana"},
    {"symbol": "XRPUSDT", "label": "XRP"},
    {"symbol": "ZECUSDT", "label": "Zcash"},
]
DEFAULT_INTERVAL = "15m"
LIMIT = 200

# -----------------------------
# Data fetch
# -----------------------------
def fetch_klines(symbol: str, interval: str = DEFAULT_INTERVAL, limit: int = LIMIT) -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    raw = r.json()
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_asset_volume","trades","taker_buy_base",
        "taker_buy_quote","ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df

# -----------------------------
# Indicators
# -----------------------------
def compute_indicators(df: pd.DataFrame):
    df["rsi"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd["MACD_12_26_9"]
    df["macd_signal"] = macd["MACDs_12_26_9"]
    df["macd_hist"] = macd["MACDh_12_26_9"]
    psar = ta.psar(df["high"], df["low"], df["close"])
    df["psar"] = psar["PSARl_0.02_0.2"].fillna(psar["PSARs_0.02_0.2"])
    return df

# -----------------------------
# Simple confirmation bundle
# -----------------------------
def confirmation_bundle(df: pd.DataFrame):
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    rsi = latest["rsi"]

    macd_cross_up = (prev["macd"] < prev["macd_signal"]) and (latest["macd"] > latest["macd_signal"])
    macd_cross_down = (prev["macd"] > prev["macd_signal"]) and (latest["macd"] < latest["macd_signal"])
    price_above_psar = latest["close"] > latest["psar"]
    price_below_psar = latest["close"] < latest["psar"]

    buy_ok = (pd.notna(rsi) and rsi < 40) and macd_cross_up and price_above_psar
    sell_ok = (pd.notna(rsi) and rsi > 60) and macd_cross_down and price_below_psar

    return {
        "price": float(latest["close"]),
        "time": latest["close_time"],
        "rsi": float(rsi) if pd.notna(rsi) else None,
        "macd": float(latest["macd"]) if pd.notna(latest["macd"]) else None,
        "macd_signal": float(latest["macd_signal"]) if pd.notna(latest["macd_signal"]) else None,
        "macd_hist": float(latest["macd_hist"]) if pd.notna(latest["macd_hist"]) else None,
        "psar": float(latest["psar"]) if pd.notna(latest["psar"]) else None,
        "buy_ok": buy_ok,
        "sell_ok": sell_ok,
    }

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Multi-Asset Trading Assistant", layout="wide")
st.title("Multi-Asset Trading Assistant (ETH, SOL, XRP, ZEC)")

interval = st.sidebar.selectbox("Interval", ["1m","5m","15m","30m","1h","4h","1d"], index=2)
refresh_sec = st.sidebar.slider("Auto-refresh seconds", 0, 120, 0)
show_tables = st.sidebar.checkbox("Show raw data tables", False)

cols = st.columns(2)
for i, asset in enumerate(ASSETS):
    with cols[i % 2]:
        st.markdown(f"### {asset['label']} ({asset['symbol']})")
        df = fetch_klines(asset["symbol"], interval=interval)
        df = compute_indicators(df)
        bundle = confirmation_bundle(df)

        st.metric("Price", f"{bundle['price']:.4f}")
        st.write(f"RSI: {bundle['rsi']:.2f} | MACD: {bundle['macd']:.4f} | Signal: {bundle['macd_signal']:.4f} | Hist: {bundle['macd_hist']:.4f}")

        st.success("BUY conditions met") if bundle["buy_ok"] else st.info("Buy not confirmed")
        st.error("SELL conditions met") if bundle["sell_ok"] else st.info("Sell not confirmed")

        st.line_chart(df[["close","psar"]].set_index(df["close_time"]))

        if show_tables:
            st.dataframe(df.tail(50))

if refresh_sec > 0:
    st.caption(f"Auto-refreshing every {refresh_sec} seconds…")
    time.sleep(refresh_sec)
    st.experimental_rerun()
