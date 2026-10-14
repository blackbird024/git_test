"""Descarga (DE PAGO, autorizada por el usuario el 14-oct-2026; coste consultado ≈ 10,41 USD) de FDAX.c.0 ohlcv-1m de
Databento XEUR.EOBI (Eurex), 2025-03-10 → 2026-10-13 22:00 UTC (todo lo disponible). Continuo por calendario, sin ajuste.
Se guarda en vwap_lab/data/cache/ (ignorado por git)."""
import os
from pathlib import Path

import databento as db

OUT = Path(__file__).resolve().parents[2] / "vwap_lab" / "data" / "cache"
OUT.mkdir(parents=True, exist_ok=True)
c = db.Historical(os.environ["DATABENTO_API_KEY"])
sym = "FDAX.c.0"
raw = OUT / "FDAX_c_0_1m.pkl"
if raw.exists():
    print(sym, "ya descargado", raw)
else:
    kw = dict(dataset="XEUR.EOBI", symbols=[sym], stype_in="continuous", schema="ohlcv-1m",
              start="2025-03-10", end="2026-10-13T22:00")
    print(sym, "coste:", c.metadata.get_cost(**kw), flush=True)
    df = c.timeseries.get_range(**kw).to_df()
    df.to_pickle(raw)
    print(sym, len(df), df.index[0], df.index[-1], "→", raw, flush=True)
