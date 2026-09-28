"""Carga de las velas descargadas y paso a hora de Nueva York.

Por qué hora de NY: todas las reglas (apertura 9:30, cierre forzado 15:50) están en hora de NY,
y así los cambios de horario de verano quedan resueltos automáticamente.
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
TZ = "America/New_York"


def load_minutes(root: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Velas de 1 minuto de `root` ("NQ" o "GC") con índice en hora de NY."""
    files = sorted(RAW.glob(f"{root}_1m_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No hay datos de {root} en {RAW}. Ejecuta scripts/download_databento.py")
    df = pd.concat(pd.read_parquet(f) for f in files).sort_index()
    df.index = df.index.tz_convert(TZ)
    df = df[~df.index.duplicated(keep="last")]
    if start:
        df = df[df.index >= pd.Timestamp(start, tz=TZ)]
    if end:
        df = df[df.index < pd.Timestamp(end, tz=TZ)]
    return df
