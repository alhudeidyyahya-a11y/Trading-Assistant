import time
import requests
import pandas as pd
import pandas_ta as ta
import streamlit as st

# -----------------------------
# Config
# -----------------------------
ASSETS = [
    {"symbol": "ETHUSDT", "label": "Ethereum", "id": "ethereum"},
    {"symbol": "SOLUSDT", "label": "Solana", "id": "solana"},
    {"symbol": "XRPUSDT", "label": "XRP", "id": "ripple"},
    {"symbol": "ZECUSDT", "label": "Zcash", "id": "zcash"},
]

DEFAULT_INTERVAL = "minute"  # CoinGecko supports: 'minute', 'hourly', 'daily'
DAYS = "1"  # how many days of data to fetch

# -----------------------------
# Data fetch from CoinGecko
# -----------------------------
def fetch_klines(asset_id: str, interval: str = DEFAULT_INTERVAL, days: str = DAYS) -> pd.DataFrame:
    url = f"https://api.coingecko.com/api/v3/coins/{asset_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": interval}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        st.error(f"Failed to fetch data for {asset_id}: {e}")
        return pd.DataFrame()

    # CoinGecko returns [timestamp, price]
    prices = raw.get("prices", [])
    df = pd.DataFrame(prices, columns=["time", "close"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    return df

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
    # PSAR normally needs high/low, but we only have close → use trailing close as placeholder
    df["psar"] = df["close"].shift(1)
    return df

# -----------------------------
# Confirmation bundle
# -----------------------------
def confirmation_bundle(df: pd.DataFrame):
    if df.empty:
        return {}
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
        "time": latest["time"],
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

interval = st.sidebar.selectbox("Interval", ["minute","hourly","daily"], index=0)
days = st.sidebar.selectbox("Days of history", ["1","7","30"], index=0)
refresh_sec = st.sidebar.slider("Auto-refresh seconds", 0, 120, 0)
show_tables = st.sidebar.checkbox("Show raw data tables", False)

cols = st.columns(2)
for i, asset in enumerate(ASSETS):
    with cols[i % 2]:
        st.markdown(f"### {asset['label']} ({asset['symbol']})")
        df = fetch_klines(asset["id"], interval=interval, days=days)
        df = compute_indicators(df)
        bundle = confirmation_bundle(df)

        if not bundle:
            st.warning("No data available")
            continue

        st.metric("Price (USD)", f"{bundle['price']:.4f}")
        st.write(f"RSI: {bundle['rsi']:.2f} | MACD: {bundle['macd']:.4f} | Signal: {bundle['macd_signal']:.4f} | Hist: {bundle['macd_hist']:.4f}")

        st.success("BUY conditions met") if bundle["buy_ok"] else st.info("Buy not confirmed")
        st.error("SELL conditions met") if bundle["sell_ok"] else st.info("Sell not confirmed")

        st.line_chart(df[["close","psar"]].set_index(df["time"]))

        if show_tables:
            st.dataframe(df.tail(50))

if refresh_sec > 0:
    st.caption(f"Auto-refreshing every {refresh_sec} seconds…")
    time.sleep(refresh_sec)
    st.experimental_rerun()
