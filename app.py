from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_TITLE = "BTC Trading Simulator"
INITIAL_CASH = 10_000.0
MAX_PRICE_POINTS = 100
TRADE_SIZE_BTC = 0.001
REFRESH_SECONDS = 5
REQUEST_TIMEOUT = 6

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
COINBASE_URL = "https://api.coinbase.com/v2/prices/BTC-USD/spot"


@dataclass
class Portfolio:
    cash: float
    btc: float

    @property
    def position_value(self) -> float:
        return self.btc

    def total_value(self, btc_price: float) -> float:
        return self.cash + self.btc * btc_price


@dataclass
class Trade:
    timestamp: datetime
    side: str
    price: float
    quantity: float
    reason: str


class PriceFeed:
    def __init__(self) -> None:
        self.sources = [
            ("CoinGecko", self._from_coingecko),
            ("Binance", self._from_binance),
            ("Coinbase", self._from_coinbase),
        ]

    def get_price(self) -> Tuple[Optional[float], str, List[str]]:
        errors: List[str] = []
        for name, provider in self.sources:
            try:
                value = provider()
                if value is not None and value > 0:
                    return float(value), name, errors
                errors.append(f"{name}: invalid price payload")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
        return None, "Fallback", errors

    def _from_coingecko(self) -> Optional[float]:
        response = requests.get(COINGECKO_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return float(response.json()["bitcoin"]["usd"])

    def _from_binance(self) -> Optional[float]:
        response = requests.get(BINANCE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return float(response.json()["price"])

    def _from_coinbase(self) -> Optional[float]:
        response = requests.get(COINBASE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return float(response.json()["data"]["amount"])


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    gain_series = pd.Series(gain, index=prices.index)
    loss_series = pd.Series(loss, index=prices.index)

    avg_gain = gain_series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss_series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def build_features(price_history: Deque[float]) -> pd.DataFrame:
    df = pd.DataFrame({"price": list(price_history)})
    df["ma_5"] = df["price"].rolling(5).mean()
    df["ma_10"] = df["price"].rolling(10).mean()
    df["rsi_14"] = compute_rsi(df["price"], period=14)
    return df


def make_decision(df: pd.DataFrame) -> Tuple[str, str]:
    if len(df) < 15:
        return "HOLD", "Insufficient candles for MA/RSI confirmation"

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    bullish_cross = prev["ma_5"] <= prev["ma_10"] and latest["ma_5"] > latest["ma_10"]
    bearish_cross = prev["ma_5"] >= prev["ma_10"] and latest["ma_5"] < latest["ma_10"]

    if bullish_cross and latest["rsi_14"] < 70:
        return "BUY", "MA(5) crossed above MA(10) and RSI below 70"
    if bearish_cross and latest["rsi_14"] > 30:
        return "SELL", "MA(5) crossed below MA(10) and RSI above 30"
    return "HOLD", "No confirmed crossover + RSI filter"


def execute_trade(
    portfolio: Portfolio,
    decision: str,
    price: float,
    reason: str,
    trade_size: float = TRADE_SIZE_BTC,
) -> Optional[Trade]:
    now = datetime.now(timezone.utc)

    if decision == "BUY":
        cost = price * trade_size
        if portfolio.cash >= cost:
            portfolio.cash -= cost
            portfolio.btc += trade_size
            return Trade(now, "BUY", price, trade_size, reason)

    if decision == "SELL" and portfolio.btc >= trade_size:
        proceeds = price * trade_size
        portfolio.cash += proceeds
        portfolio.btc -= trade_size
        return Trade(now, "SELL", price, trade_size, reason)

    return None


def init_state() -> None:
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = Portfolio(cash=INITIAL_CASH, btc=0.0)
    if "trades" not in st.session_state:
        st.session_state.trades: List[Trade] = []
    if "price_history" not in st.session_state:
        st.session_state.price_history = deque(maxlen=MAX_PRICE_POINTS)
    if "last_known_price" not in st.session_state:
        st.session_state.last_known_price = 30_000.0
    if "last_source" not in st.session_state:
        st.session_state.last_source = "Fallback"
    if "errors" not in st.session_state:
        st.session_state.errors = []


def render(trading_df: pd.DataFrame, current_price: float, source: str, decision: str, reason: str) -> None:
    st.title("₿ Production Trading Simulator")
    st.caption("Live multi-API BTC feed + resilient fallback + strategy-based paper trading")

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Live BTC Price", f"${current_price:,.2f}", help=f"Source: {source}")
    col_b.metric("AI Decision", decision)
    col_c.metric("Data Source", source)

    portfolio: Portfolio = st.session_state.portfolio
    total_value = portfolio.total_value(current_price)

    m1, m2, m3 = st.columns(3)
    m1.metric("Portfolio Value", f"${total_value:,.2f}")
    m2.metric("Cash", f"${portfolio.cash:,.2f}")
    m3.metric("BTC Position", f"{portfolio.btc:.6f} BTC")

    st.info(f"Strategy rationale: {reason}")

    chart_df = trading_df.copy()
    chart_df.index = pd.RangeIndex(start=max(1, len(chart_df) - len(chart_df) + 1), stop=len(chart_df) + 1)
    st.subheader("Price & Moving Averages")
    st.line_chart(chart_df[["price", "ma_5", "ma_10"]])

    st.subheader("Recent Indicators")
    latest = trading_df.iloc[-1]
    i1, i2, i3 = st.columns(3)
    i1.metric("MA (5)", f"{latest['ma_5']:.2f}" if pd.notna(latest["ma_5"]) else "n/a")
    i2.metric("MA (10)", f"{latest['ma_10']:.2f}" if pd.notna(latest["ma_10"]) else "n/a")
    i3.metric("RSI (14)", f"{latest['rsi_14']:.2f}" if pd.notna(latest["rsi_14"]) else "n/a")

    st.subheader("Trade History")
    if st.session_state.trades:
        trade_df = pd.DataFrame(
            [
                {
                    "Timestamp (UTC)": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Side": t.side,
                    "Price": round(t.price, 2),
                    "Quantity BTC": t.quantity,
                    "Notional USD": round(t.price * t.quantity, 2),
                    "Reason": t.reason,
                }
                for t in reversed(st.session_state.trades)
            ]
        )
        st.dataframe(trade_df, use_container_width=True, hide_index=True)
    else:
        st.write("No simulated trades yet.")

    if st.session_state.errors:
        with st.expander("API Failures (resilient fallback active)"):
            for error in st.session_state.errors[-10:]:
                st.warning(error)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    init_state()

    feed = PriceFeed()
    price, source, errors = feed.get_price()

    if price is None:
        price = float(st.session_state.last_known_price)
        source = "Fallback (last known price)"
        errors.append("All providers unavailable. Using last known price.")
    else:
        st.session_state.last_known_price = float(price)

    st.session_state.last_source = source
    st.session_state.errors.extend(errors)

    st.session_state.price_history.append(float(price))

    trading_df = build_features(st.session_state.price_history)
    decision, reason = make_decision(trading_df)

    trade = execute_trade(st.session_state.portfolio, decision, float(price), reason)
    if trade:
        st.session_state.trades.append(trade)

    render(trading_df, float(price), source, decision, reason)

    st.caption(f"Auto-refreshing every {REFRESH_SECONDS} seconds.")
    st.autorefresh(interval=REFRESH_SECONDS * 1000, key="sim-refresh")


if __name__ == "__main__":
    main()
