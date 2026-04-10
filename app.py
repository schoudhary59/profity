import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="SafeTrade AI PRO", layout="wide")

st.title("🚀 SafeTrade AI — Autonomous Trading Engine")
st.caption("AI trading system with live market intelligence")

# =============================
# SESSION STATE
# =============================
if "cash" not in st.session_state:
    st.session_state.cash = 10000.0

if "position" not in st.session_state:
    st.session_state.position = 0.0

if "history" not in st.session_state:
    st.session_state.history = []

if "price_history" not in st.session_state:
    st.session_state.price_history = []

# =============================
# FETCH PRICE (ULTRA STABLE)
# =============================
def fetch_price():
    headers = {"User-Agent": "Mozilla/5.0"}

    # CoinGecko
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()["bitcoin"]["usd"]
        else:
            st.warning(f"CoinGecko failed: {r.status_code}")
    except Exception as e:
        st.warning(f"CoinGecko error: {e}")

    # Binance
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return float(r.json()["price"])
        else:
            st.warning(f"Binance failed: {r.status_code}")
    except Exception as e:
        st.warning(f"Binance error: {e}")

    # Coinbase (MOST RELIABLE)
    try:
        r = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return float(r.json()["data"]["amount"])
        else:
            st.warning(f"Coinbase failed: {r.status_code}")
    except Exception as e:
        st.warning(f"Coinbase error: {e}")

    return None

# =============================
# GET PRICE WITH FALLBACK
# =============================
price = fetch_price()

if price is None:
    st.warning("⚠️ Live data unavailable — using fallback system")

    if st.session_state.price_history:
        price = st.session_state.price_history[-1]
    else:
        price = 30000  # default fallback

# Store history
st.session_state.price_history.append(price)
st.session_state.price_history = st.session_state.price_history[-100:]

st.subheader(f"💰 BTC Price: ${price:.2f}")

# =============================
# DATAFRAME
# =============================
df = pd.DataFrame(st.session_state.price_history, columns=["price"])

# =============================
# AI STRATEGY (MOVING AVERAGE)
# =============================
def ai_decision(df):
    if len(df) < 10:
        return "HOLD"

    df["ma_short"] = df["price"].rolling(5).mean()
    df["ma_long"] = df["price"].rolling(10).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    if prev["ma_short"] < prev["ma_long"] and latest["ma_short"] > latest["ma_long"]:
        return "BUY"

    elif prev["ma_short"] > prev["ma_long"] and latest["ma_short"] < latest["ma_long"]:
        return "SELL"

    return "HOLD"

decision = ai_decision(df)

st.write(f"🤖 AI Decision: **{decision}**")

# =============================
# EXECUTE TRADE
# =============================
qty = 0.001

if decision == "BUY" and st.session_state.cash >= price * qty:
    st.session_state.cash -= price * qty
    st.session_state.position += qty
    st.session_state.history.append((datetime.now(), "BUY", price))

elif decision == "SELL" and st.session_state.position >= qty:
    st.session_state.cash += price * qty
    st.session_state.position -= qty
    st.session_state.history.append((datetime.now(), "SELL", price))

# =============================
# PORTFOLIO
# =============================
portfolio_value = st.session_state.cash + (st.session_state.position * price)

col1, col2, col3 = st.columns(3)
col1.metric("💼 Portfolio Value", f"${portfolio_value:.2f}")
col2.metric("💵 Cash", f"${st.session_state.cash:.2f}")
col3.metric("📦 BTC Holding", f"{st.session_state.position:.6f}")

# =============================
# CHART
# =============================
st.subheader("📊 Price Chart")
st.line_chart(df["price"])

# =============================
# TRADE HISTORY
# =============================
st.subheader("📜 Trade History")

if st.session_state.history:
    hist_df = pd.DataFrame(
        st.session_state.history, columns=["Time", "Action", "Price"]
    )
    st.dataframe(hist_df)
else:
    st.write("No trades yet")

# =============================
# AUTO REFRESH LOOP
# =============================
time.sleep(3)
st.rerun()
