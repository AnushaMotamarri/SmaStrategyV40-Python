
# import warnings
# warnings.filterwarnings("ignore",category=FutureWarning)
# # # show list of stocks whose closing price <= sma_20 <= sma_50 <= sma_200
# # # sell condition: when closing price>=sma_20>=sma_50>=sma_200
# from fastapi import FastAPI
# import yfinance as yf
# import pandas as pd
# import numpy as np
# import os
# from fastapi.responses import JSONResponse
# import datetime
# app = FastAPI()

# CSV_PATH = "./40stocks.csv"
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # or restrict to ["http://localhost:3000"] etc.
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# def load_tickers():
#     with open("40stocks.csv", "r") as f:
#         content = f.read().strip()
#         tickers = [t.strip() for t in content.split(",") if t.strip()]
#     return tickers

# def truncate_to_2_decimals(value):
#     return np.floor(value * 100) / 100

# def safe_float(val):
#     try:
#         if isinstance(val, pd.Series):
#             return float(val.iloc[0])
#         return float(val)
#     except Exception:
#         return None

# def get_smas_from_adj_close(ticker, periods=[200, 50, 20]):
#     try:
#         df = yf.download(ticker, period="1y", auto_adjust=False, progress=False)
#         if df.empty or 'Adj Close' not in df.columns:
#             return None

#         adj_close_trunc = df['Adj Close'].apply(truncate_to_2_decimals)
#         sma_results = {}

#         for p in periods:
#             if len(adj_close_trunc) >= p:
#                 sma_value = adj_close_trunc.tail(p).mean()
#                 sma_value = sma_value.iloc[0]
#                 sma_results[f'sma_{p}'] = round(sma_value, 4)
#             else:
#                 sma_results[f'sma_{p}'] = None

#         latest_close = float(adj_close_trunc.iloc[-1])
#         return {
#             "ticker": ticker,
#             "close": latest_close,
#             **sma_results
#         }
#     except:
#         return None

# def check_buy_signal(data):
#     close = safe_float(data.get("close"))
#     s20 = safe_float(data.get("sma_20"))
#     s50 = safe_float(data.get("sma_50"))
#     s200 = safe_float(data.get("sma_200"))
#     if None in [close, s20, s50, s200]:
#         return None
#     return "BUY" if close <= s20 <= s50 <= s200 else None

# def check_sell_signal(data):
#     close = safe_float(data.get("close"))
#     s20 = safe_float(data.get("sma_20"))
#     s50 = safe_float(data.get("sma_50"))
#     s200 = safe_float(data.get("sma_200"))
#     if None in [close, s20, s50, s200]:
#         return None
#     return "SELL" if close >= s20 >= s50 >= s200 else None

# @app.api_route("/ping", methods=["GET", "POST", "HEAD"])
# async def ping():
#     return JSONResponse(content={"status": "ok"})

# @app.get("/sma/all")
# def get_all_smas():
#     tickers = load_tickers()
#     results = []
#     count=0
#     for ticker in tickers:
#         NSE_ticker = ticker+'.NS'
#         data = get_smas_from_adj_close(NSE_ticker)
#         if not data:
#             continue
#         count+=1
#         signal = check_buy_signal(data) or check_sell_signal(data) or "NO_SIGNAL"
#         results.append({
#             "ticker": ticker,
#             "last_closing_price": data["close"],
#             "sma_20": data["sma_20"],
#             "sma_50": data["sma_50"],
#             "sma_200": data["sma_200"],
#             "signal": signal,
#         })

#     return {'results':results,'last_updated_time':datetime.datetime.now()}
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_PATH = "./40stocks.csv"

def load_tickers():
    with open(CSV_PATH, "r") as f:
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

def compute_smas(df, periods=[20, 50, 200]):
    results = []
    for ticker in df.columns:
        series = df[ticker].dropna()
        if series.empty:
            continue

        smas = {}
        for p in periods:
            if len(series) >= p:
                smas[f"sma_{p}"] = round(series.tail(p).mean(), 4)
            else:
                smas[f"sma_{p}"] = None

        smas["ticker"] = ticker
        smas["close"] = round(series.iloc[-1], 2)
        results.append(smas)
    return results

@app.api_route("/ping", methods=["GET", "POST", "HEAD"])
async def ping():
    return JSONResponse(content={"status": "ok"})

@app.get("/sma/all")
def get_all_smas():
    raw_tickers = load_tickers()
    yf_tickers = [t + ".NS" for t in raw_tickers]

    try:
        df = yf.download(yf_tickers, period="1y", auto_adjust=False, progress=False)
        adj_close = df["Adj Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Adj Close"]]
        if not isinstance(adj_close, pd.DataFrame):
            adj_close = adj_close.to_frame()

        adj_close = adj_close.applymap(truncate_to_2_decimals)
        sma_data = compute_smas(adj_close)

        results = []
        for item in sma_data:
            ticker_raw = item["ticker"].replace(".NS", "")
            signal = check_buy_signal(item) or check_sell_signal(item) or "NO_SIGNAL"
            results.append({
                "ticker": ticker_raw,
                "last_closing_price": item["close"],
                "sma_20": item.get("sma_20"),
                "sma_50": item.get("sma_50"),
                "sma_200": item.get("sma_200"),
                "signal": signal
            })

        return {
            "results": results,
            "last_updated_time": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}
