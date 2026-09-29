"""Cargadores de velas de 1 minuto. Salida común para cualquier fuente:
índice en UTC (inicio de la vela) y columnas open, high, low, close, volume (+ instrument_id si existe).

Fuentes:
  - Databento (futuros de CME): data/raw/<RAIZ>_1m_<AÑO>.parquet, ya en UTC, con volumen real.
  - MT5: CSV con <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> en hora del servidor
    (UTC+2 en invierno, UTC+3 en verano). OJO: <TICKVOL> es el número de cambios de precio, no el volumen.
"""
from pathlib import Path

import pandas as pd

from src.horas import NUEVA_YORK, UTC

RAIZ = Path(__file__).resolve().parent.parent.parent
COLUMNAS = ["open", "high", "low", "close", "volume"]


# ------------------------------------------------------------------------------- Databento
def cargar_databento(raiz: str, carpeta: Path = RAIZ / "data" / "raw") -> pd.DataFrame:
    archivos = sorted(carpeta.glob(f"{raiz}_1m_*.parquet"))
    if not archivos:
        raise FileNotFoundError(f"No hay datos de {raiz} en {carpeta}")
    df = pd.concat(pd.read_parquet(f) for f in archivos).sort_index()
    df.index = df.index.tz_convert(UTC)
    df.index.name = "tiempo_utc"
    cols = COLUMNAS + (["instrument_id"] if "instrument_id" in df else [])
    return df[cols]


# ------------------------------------------------------------------------------------- MT5
def servidor_a_utc(hora_servidor: pd.Series, regla_dst: str = "EEUU") -> pd.DatetimeIndex:
    """Convierte la hora del servidor de MT5 (sin zona) a UTC.

    regla_dst = "EEUU":   el servidor es UTC+3 cuando Nueva York está en horario de verano (lo más habitual:
                          así la sesión de CME cierra a medianoche del servidor).
    regla_dst = "Europa": el servidor sigue el horario de verano europeo (equivale a Europe/Athens).
    """
    naive = pd.DatetimeIndex(hora_servidor)
    if regla_dst == "Europa":
        return naive.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="NaT").tz_convert(UTC)
    if regla_dst != "EEUU":
        raise ValueError("regla_dst debe ser 'EEUU' o 'Europa'")
    supuesto = (naive - pd.Timedelta(hours=2)).tz_localize(UTC)            # si fuera invierno
    verano_ny = pd.Series(supuesto.tz_convert(NUEVA_YORK).map(lambda t: t.dst() != pd.Timedelta(0)))
    desfase = pd.to_timedelta(verano_ny.map({True: 3, False: 2}).to_numpy(), unit="h")
    return (naive - desfase).tz_localize(UTC)


def cargar_mt5(ruta: str | Path, regla_dst: str = "EEUU") -> pd.DataFrame:
    """Lee un CSV exportado de MT5 (separado por tabuladores o comas, con o sin segundos)."""
    df = pd.read_csv(ruta, sep=None, engine="python")
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    fecha = df["date"].astype(str).str.replace(".", "-", regex=False)
    hora = pd.to_datetime(fecha + " " + df["time"].astype(str), format="mixed")
    indice = servidor_a_utc(hora, regla_dst)
    out = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce") for c in ["open", "high", "low", "close"]})
    out["volume"] = pd.to_numeric(df.get("tickvol", df.get("vol", 0)), errors="coerce")
    out.index = indice
    out.index.name = "tiempo_utc"
    return out[out.index.notna()].sort_index()
