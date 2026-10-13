"""Descarga (DE PAGO, autorizada por el usuario el 13-oct-2026; coste consultado: 6E ≈ 11,10 USD, 6B ≈ 10,45 USD) de
6E.v.0 (EUR/USD) y 6B.v.0 (GBP/USD) ohlcv-1m de Databento GLBX.MDP3, 2018-01-01 → 2026-10-03.
Continuo por VOLUMEN, sin ajuste de rollover. Se guarda en vwap_lab/data/cache/ (ignorado por git, como el GC)."""
import os
from pathlib import Path

import databento as db

OUT = Path(__file__).resolve().parents[2] / "vwap_lab" / "data" / "cache"
OUT.mkdir(parents=True, exist_ok=True)
c = db.Historical(os.environ["DATABENTO_API_KEY"])
for sym in ("6E.v.0", "6B.v.0"):
    raw = OUT / f"{sym.replace('.', '_')}_1m.pkl"
    if raw.exists():
        print(sym, "ya descargado", raw)
        continue
    kw = dict(dataset="GLBX.MDP3", symbols=[sym], stype_in="continuous", schema="ohlcv-1m",
              start="2018-01-01", end="2026-10-03")
    print(sym, "coste:", c.metadata.get_cost(**kw), flush=True)
    df = c.timeseries.get_range(**kw).to_df()
    df.to_pickle(raw)
    print(sym, len(df), df.index[0], df.index[-1], "→", raw, flush=True)
