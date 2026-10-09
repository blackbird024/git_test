"""Descarga gratuita (Alpaca, feed SIP) de velas diarias de ETF estadounidenses usadas como proxy del Nasdaq-100.

Solo datos gratuitos con la cuenta de Alpaca ya configurada (APCA_API_KEY_ID / APCA_API_SECRET_KEY en el entorno).
Guarda dos versiones en data/cache/: precios brutos (raw) y ajustados por dividendos y splits (all).

Uso:
    python data/fetch_etf_daily.py QQQ
"""
import os
import sys
from datetime import datetime
from pathlib import Path

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

CACHE = Path(__file__).resolve().parent / "cache"


def fetch(symbol, adjustment):
    client = StockHistoricalDataClient(os.environ["APCA_API_KEY_ID"], os.environ["APCA_API_SECRET_KEY"])
    req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Day, start=datetime(2015, 1, 1),
                           feed=DataFeed.SIP, adjustment=adjustment)
    df = client.get_stock_bars(req).df.reset_index()
    df["day"] = df["timestamp"].dt.tz_convert("America/New_York").dt.date
    return df.set_index("day")[["open", "high", "low", "close", "volume"]]


if __name__ == "__main__":
    CACHE.mkdir(exist_ok=True)
    for sym in sys.argv[1:] or ["QQQ"]:
        for adj, tag in ((Adjustment.RAW, "raw"), (Adjustment.ALL, "adj")):
            df = fetch(sym, adj)
            df.to_pickle(CACHE / f"{sym}_daily_{tag}.pkl")
            print(sym, tag, df.index[0], df.index[-1], len(df))
