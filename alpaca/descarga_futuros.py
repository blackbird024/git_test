"""Descarga velas de 1 min de Databento (GLBX.MDP3, contrato continuo por volumen de fecha) y las guarda en 5 min (hora NY).

Uso:
    python descarga_futuros.py RTY YM CL SI HG 6E ZN NG
"""

import os
import pickle
import sys
from pathlib import Path

import databento as db
import pandas as pd

CACHE = Path(__file__).parent / ".lab_cache"


def main():
    c = db.Historical(os.environ["DATABENTO_API_KEY"])
    for sym in sys.argv[1:]:
        out = CACHE / f"dbn_{sym}_5m.pkl"
        if out.exists():
            print(sym, "ya existe")
            continue
        data = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=[f"{sym}.c.0"], stype_in="continuous", schema="ohlcv-1m",
                                      start="2018-01-01", end="2026-10-03")
        df = data.to_df()
        df.index = df.index.tz_convert("America/New_York")
        b = df.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        out.write_bytes(pickle.dumps(b[["open", "high", "low", "close", "volume"]]))
        print(sym, len(df), "velas 1m →", len(b), "velas 5m", b.index.min(), b.index.max(), flush=True)


if __name__ == "__main__":
    main()
