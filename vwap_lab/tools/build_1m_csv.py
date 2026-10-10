"""CSV de 1 min con volumen para el experimento en 1 minuto (no descarga nada).
MNQ: laboratorio/data/cache/nq_1m_et.pkl (NQ.c.0). MGC: vwap_lab/data/cache/GC_v0_1m.pkl (GC.v.0, comprado)."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "vwap_lab" / "data" / "cache"
for sym, src in (("MNQ", ROOT / "laboratorio" / "data" / "cache" / "nq_1m_et.pkl"), ("MGC", OUT / "GC_v0_1m.pkl")):
    df = pd.read_pickle(src)
    out = df[["open", "high", "low", "close", "volume"]].copy()
    out.index = out.index.tz_convert("America/New_York")
    out["contract"] = df["instrument_id"].astype(str).to_numpy()
    out.insert(0, "timestamp", out.index.map(lambda t: t.isoformat()))
    out.to_csv(OUT / f"{sym}_1m.csv", index=False)
    print(sym, len(out), "→", OUT / f"{sym}_1m.csv")
