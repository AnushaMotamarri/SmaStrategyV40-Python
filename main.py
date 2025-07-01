
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import Body

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_PATH = "./40stocks.csv"
Week_52_PATH = './52WeekStrategy.csv'
V20_Strategy_file = './v20StrategyTickers.csv'
def load_tickers(path):
    with open(path, "r") as f:
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
    raw_tickers = load_tickers(CSV_PATH)
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


class ResearchInput(BaseModel):
    ticker: str
    buyPrice: float
    targetPrice: float
    reportDate: str  # Example format: "01/01/24"


@app.post("/research-stock")
def research_stock(inputs: List[ResearchInput] = Body(...)):
    results = []

    for item in inputs:
        ticker = item.ticker + ".NS"
        try:
            # Format report date to datetime
            report_date = datetime.datetime.strptime(item.reportDate, "%d/%m/%Y")

            # Fetch data from report date till today
            df = yf.download(ticker, start=report_date.strftime('%Y-%m-%d'), auto_adjust=False, progress=False)

            if df.empty or 'Adj Close' not in df.columns:
                raise Exception("No data available for given ticker or date range")

            current_price = df['Adj Close'].dropna().iloc[-1]
            adjCurrentPrice = round(float(current_price), 2)

            actualOpportunity = ((item.targetPrice - item.buyPrice) / item.buyPrice) * 100
            currentOpportunity = ((item.targetPrice - adjCurrentPrice) / adjCurrentPrice) * 100
            opportunityVariation = ((adjCurrentPrice - item.buyPrice) / item.buyPrice) * 100

            # ✅ Find the first date when High >= targetPrice
            target_touch_date = None
            filtered = df[('High',ticker)]
            highs = df[filtered >= float(item.targetPrice)]
            if not highs.empty:
                target_touch_date = highs.index[0].strftime("%d-%m-%Y")

            results.append({
                "ticker": item.ticker,
                "current_price": adjCurrentPrice,
                "actual_opportunity": round(float(actualOpportunity), 2),
                "current_opportunity": round(float(currentOpportunity), 2),
                "opportunity_variation": round(float(opportunityVariation), 2),
                "buy_price":item.buyPrice,
                "target_price":item.targetPrice,
                "report_date":item.reportDate,
                "target_price_hit_date": target_touch_date if target_touch_date else "Not Yet"  # None if never hit
            })

        except Exception as e:
            results.append({
                "ticker": item.ticker,
                "error": str(e),
            })

    return results

@app.get("/v20")
def get_v20_shares():
    raw_tickers = load_tickers(Week_52_PATH)
    yf_tickers = [t + ".NS" for t in raw_tickers]
    try:
        df = yf.download(yf_tickers, period="1y", auto_adjust=False, progress=False)["Close"]
    except Exception as e:
        return {"error": str(e)}

    result = []

    for raw_ticker, yf_ticker in zip(raw_tickers, yf_tickers):
        try:
            series = df[yf_ticker].dropna()
            if series.empty:
                continue

            current_price = series.iloc[-1]
            least_price = series.min()
            highest_price = series.max()

            if current_price <= least_price:
                target = highest_price
                percentage_profit = ((target - current_price) / current_price) * 100
                result.append({
                    "ticker": raw_ticker,
                    "current_price": round(current_price, 2),
                    "least_price": round(least_price, 2),
                    "highest_price": round(highest_price, 2),
                    "target": round(target, 2) if target else "",
                    "percentage_profit": round(percentage_profit, 2) if percentage_profit else ""
                })

            
        except Exception as e:
            print(f"Error processing {raw_ticker}: {e}")
    return {"results":result}

@app.get("/v20-strategy")
def get_green_run_20():
    raw_tickers = load_tickers(V20_Strategy_file)
    yf_tickers = [t + ".NS" for t in raw_tickers]
    try:
        data = yf.download(yf_tickers, period="1y", auto_adjust=False, progress=False, group_by="ticker")
    except Exception as e:
        return {"error": str(e)}
    result = []

    for raw_ticker, yf_ticker in zip(raw_tickers, yf_tickers):
        try:
            df = data[yf_ticker].dropna()
            df = df[["Open", "Close"]]

            # Mark green candles
            df["is_green"] = df["Close"] > df["Open"]

            # Find longest recent run of consecutive green candles
            max_run = []
            temp_run = []

            for idx, row in df.iterrows():
                if row["is_green"]:
                    temp_run.append((row["Open"], row["Close"]))
                else:
                    if len(temp_run) > len(max_run):
                        max_run = temp_run
                    temp_run = []
            if len(temp_run) > len(max_run):  # In case the last run is the longest
                max_run = temp_run

            if not max_run:
                continue

            open_price = max_run[0][0]
            close_price = max_run[-1][1]

            if ((close_price - open_price) / open_price) * 100 >= 20:
                current_price = df["Close"].iloc[-1]
                target = close_price
                profit_percent = ((target - current_price) / current_price) * 100

                result.append({
                    "ticker": raw_ticker,
                    "current_price": round(current_price, 2),
                    "20_opening_price": round(open_price, 2),
                    "20_closing_price": round(close_price, 2),
                    "target": round(target, 2),
                    "profit_percent": round(profit_percent, 2)
                })

        except Exception as e:
            print(f"Error processing {raw_ticker}: {e}")
            continue

    return {"results":result}










    