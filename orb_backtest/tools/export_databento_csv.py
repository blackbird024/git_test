"""Exporta las velas de 5 min de Databento ya descargadas (alpaca/.lab_cache/dbn_{NQ,ES}_5m.pkl) al formato CSV del
proveedor. No descarga nada. Origen: GLBX.MDP3 ohlcv-1m del contrato continuo X.c.0 (calendario, sin ajuste de rollover)
agregado a 5 min con la marca en la APERTURA de la vela (alpaca/descarga_futuros.py)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for sym in sys.argv[1:] or ["NQ", "ES"]:
    df = pd.read_pickle(ROOT / "alpaca" / ".lab_cache" / f"dbn_{sym}_5m.pkl")
    df = df.tz_convert("America/New_York")
    out = df[["open", "high", "low", "close"]].copy()
    out.insert(0, "timestamp", out.index.map(lambda t: t.isoformat()))
    out["contract"] = {"GC": "GC.v.0"}.get(sym, f"{sym}.c.0")
    p = ROOT / "orb_backtest" / "data" / f"{sym}_5m_databento.csv"
    out.to_csv(p, index=False)
    print(sym, len(out), out.timestamp.iloc[0], out.timestamp.iloc[-1], "→", p)
