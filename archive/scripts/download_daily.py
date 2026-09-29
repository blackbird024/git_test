"""Descarga velas DIARIAS de una cesta diversificada de futuros (para el seguimiento de tendencia).

Uso:
    python scripts/download_daily.py               # solo muestra el coste
    python scripts/download_daily.py --confirmar   # descarga

Mercados: índices, bonos, metales, energía, divisas, agrícolas y ganado (24 futuros de CME).
Se guarda cada mercado en data/raw/daily/<RAIZ>.parquet, con instrument_id para detectar los rolls.
"""
import argparse
import os
import sys
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "daily"
MARKETS = ["ES", "NQ", "YM", "RTY", "ZN", "ZB", "ZF", "ZT", "GC", "SI", "HG", "CL", "NG", "HO",
           "6E", "6J", "6B", "6A", "6C", "ZC", "ZS", "ZW", "LE", "HE"]
START, END = "2010-06-06", "2026-09-28"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    args = ap.parse_args()
    key = os.environ.get("DATABENTO_API_KEY") or sys.exit("Falta DATABENTO_API_KEY")
    client = db.Historical(key)
    syms = [f"{m}.v.0" for m in MARKETS]
    cost = client.metadata.get_cost(dataset="GLBX.MDP3", symbols=syms, schema="ohlcv-1d",
                                    stype_in="continuous", start=START, end=END)
    print(f"{len(MARKETS)} mercados, {START} -> {END}: coste estimado ${cost:.2f}")
    if not args.confirmar:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for m, s in zip(MARKETS, syms):
        out = OUT / f"{m}.parquet"
        if out.exists():
            continue
        df = client.timeseries.get_range(dataset="GLBX.MDP3", symbols=[s], schema="ohlcv-1d",
                                         stype_in="continuous", start=START, end=END).to_df()
        df[["open", "high", "low", "close", "volume", "instrument_id"]].to_parquet(out)
        print(f"  {m}: {len(df)} días")


if __name__ == "__main__":
    main()
