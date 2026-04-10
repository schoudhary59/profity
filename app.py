import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="SafeTrade AI PRO", layout="wide")

st.title("🚀 SafeTrade AI PRO")
st.caption("Real-Time Intelligent Trading Simulator")

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
# MULTI API FETCH (REAL FIX)
# =============================
def fetch_price():
    # API 1: CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()["bitcoin"]["usd"]
    except:
        pass

    # API 2: Binance
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["price"])
    except:
        pass

    return None

# =============================
# GET PRICE
# =============================
price = fetch_price()

if price is None:
    st.error("❌ Market data unavailable (All APIs failed)")
    st.stop()

# Store history
st.session_state.price_history.append(price)

# Keep only last 100 points
st.session_state.price_history = st.session_state.price_history[-100:]

st.subheader(f"💰 BTC Price: ${price}")

# =============================
# BUILD DATAFRAME
# =============================
df = pd.DataFrame(st.session_state.price_history, columns=["price"])

# =============================
# AI STRATEGY (REAL LOGIC)
# =============================
def ai_decision(df):
    if len(df) < 10:
        return "HOLD"

    df["ma_short"] = df["price"].rolling(5).mean()
    df["ma_long"] = df["price"].rolling(10).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Golden cross
    if prev["ma_short"] < prev["ma_long"] and latest["ma_short"] > latest["ma_long"]:
        return "BUY"

    # Death cross
    elif prev["ma_short"] > prev["ma_long"] and latest["ma_short"] < latest["ma_long"]:
        return "SELL"

    else:
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
col1.metric("💼 Portfolio", f"${portfolio_value:.2f}")
col2.metric("💵 Cash", f"${st.session_state.cash:.2f}")
col3.metric("📦 BTC", f"{st.session_state.position:.6f}")

# =============================
# CHART (REAL SYSTEM FEEL)
# =============================
st.subheader("📊 Price Chart")
st.line_chart(df["price"])

# =============================
# TRADE HISTORY
# =============================
st.subheader("📜 Trade History")

if st.session_state.history:
    hist_df = pd.DataFrame(st.session_state.history, columns=["Time", "Action", "Price"])
    st.dataframe(hist_df)
else:
    st.write("No trades yet")

# =============================
# AUTO LOOP (REAL-TIME)
# =============================
time.sleep(3)
st.rerun()
