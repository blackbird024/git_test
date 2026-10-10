"""Descarga (DE PAGO, autorizada por el usuario el 10-oct-2026; coste estimado 11,16 USD) de GC.v.0 ohlcv-1m de
Databento 2018-01-01 → 2026-10-03 y construye vwap_lab/data/cache/MGC_5m.csv (precios de GC = precios de MGC).
GC.v.0 = continuo por VOLUMEN (sigue el contrato más negociado), sin ajuste de rollover."""
import os
from pathlib import Path

import databento as db
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "cache"
OUT.mkdir(parents=True, exist_ok=True)
raw = OUT / "GC_v0_1m.pkl"
if not raw.exists():
    c = db.Historical(os.environ["DATABENTO_API_KEY"])
    print("coste:", c.metadata.get_cost(dataset="GLBX.MDP3", symbols=["GC.v.0"], stype_in="continuous",
                                        schema="ohlcv-1m", start="2018-01-01", end="2026-10-03"), flush=True)
    df = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=["GC.v.0"], stype_in="continuous", schema="ohlcv-1m",
                                start="2018-01-01", end="2026-10-03").to_df()
    df.to_pickle(raw)
df = pd.read_pickle(raw)
print("1 min:", len(df), df.index[0], df.index[-1], flush=True)
g = df.groupby(df.index.floor("5min"))
out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                    "volume": g["volume"].sum(), "contract": g["instrument_id"].last().astype(str)})
out.index = out.index.tz_convert("America/New_York")
out.insert(0, "timestamp", out.index.map(lambda t: t.isoformat()))
out.to_csv(OUT / "MGC_5m.csv", index=False)
print("5 min:", len(out), "→", OUT / "MGC_5m.csv")
