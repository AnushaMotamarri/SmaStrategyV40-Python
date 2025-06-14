
import warnings
warnings.filterwarnings("ignore",category=FutureWarning)
# # show list of stocks whose closing price <= sma_20 <= sma_50 <= sma_200
# # sell condition: when closing price>=sma_20>=sma_50>=sma_200
from fastapi import FastAPI
import yfinance as yf
import pandas as pd
import numpy as np
import os

app = FastAPI()

CSV_PATH = "./40stocks.csv"

def load_tickers():
    with open("40stocks.csv", "r") as f:
        content = f.read().strip()
        tickers = [t.strip() for t in content.split(",") if t.strip()]
    return tickers

def truncate_to_2_decimals(value):
    return np.floor(value * 100) / 100

def safe_float(val):
    try:
        if isinstance(val, pd.Series):
            return float(val.iloc[0])
        return float(val)
    except Exception:
        return None

def get_smas_from_adj_close(ticker, periods=[200, 50, 20]):
    try:
        df = yf.download(ticker, period="13mo", auto_adjust=False, progress=False)
        if df.empty or 'Adj Close' not in df.columns:
            return None

        adj_close_trunc = df['Adj Close'].apply(truncate_to_2_decimals)
        sma_results = {}

        for p in periods:
            if len(adj_close_trunc) >= p:
                sma_value = adj_close_trunc.tail(p).mean()
                sma_results[f'sma_{p}'] = round(sma_value, 4)
            else:
                sma_results[f'sma_{p}'] = None

        latest_close = float(adj_close_trunc.iloc[-1])
        return {
            "ticker": ticker,
            "close": latest_close,
            **sma_results
        }
    except:
        return None

def check_buy_signal(data):
    close = safe_float(data.get("close"))
    s20 = safe_float(data.get("sma_20"))
    s50 = safe_float(data.get("sma_50"))
    s200 = safe_float(data.get("sma_200"))
    if None in [close, s20, s50, s200]:
        return None
    return "BUY" if close <= s20 <= s50 <= s200 else None

def check_sell_signal(data):
    close = safe_float(data.get("close"))
    s20 = safe_float(data.get("sma_20"))
    s50 = safe_float(data.get("sma_50"))
    s200 = safe_float(data.get("sma_200"))
    if None in [close, s20, s50, s200]:
        return None
    return "SELL" if close >= s20 >= s50 >= s200 else None

@app.get("/sma/all")
def get_all_smas():
    tickers = load_tickers()
    print(tickers)
    results = []

    for ticker in tickers:
        data = get_smas_from_adj_close(ticker+'.NS')
        if not data:
            continue

        signal = check_buy_signal(data) or check_sell_signal(data) or "NO SIGNAL"
        results.append({
            "ticker": data["ticker"],
            "last_closing_price": data["close"],
            "sma_20": data["sma_20"],
            "sma_50": data["sma_50"],
            "sma_200": data["sma_200"],
            "signal": signal
        })

    return results
