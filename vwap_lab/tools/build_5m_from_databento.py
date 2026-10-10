"""Construye velas de 5 min CON VOLUMEN desde las velas de 1 min de Databento ya descargadas (no descarga nada).

NQ: alpaca/.lab_cache/databento_nq_1m_2018_2024.pkl + databento_glbx_1m.pkl (símbolo NQ.c.0), unidas en
laboratorio/data/cache/nq_1m_et.pkl. Columna `contract` = instrument_id de Databento (cambia en cada rollover).
Agregación: open = primera, high = máx., low = mín., close = última, volume = suma; marca = APERTURA de la vela de 5 min.
Los minutos sin operaciones no existen en el origen: una vela de 5 min se crea si hubo al menos una operación.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "vwap_lab" / "data" / "cache"


def build_nq():
    src = ROOT / "laboratorio" / "data" / "cache" / "nq_1m_et.pkl"
    if not src.exists():
        sys.path.insert(0, str(ROOT / "laboratorio"))
        from data.loaders import nq_1m          # crea la caché unida a partir de los dos archivos originales
        df = nq_1m()
    else:
        df = pd.read_pickle(src)
    g = df.groupby(df.index.floor("5min"))
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum(),
                        "contract": g["instrument_id"].last().astype(str)})
    OUT.mkdir(parents=True, exist_ok=True)
    out.insert(0, "timestamp", out.index.map(lambda t: t.isoformat()))
    p = OUT / "MNQ_5m.csv"
    out.to_csv(p, index=False)
    print("MNQ", len(out), out.timestamp.iloc[0], out.timestamp.iloc[-1], "→", p)


if __name__ == "__main__":
    build_nq()
