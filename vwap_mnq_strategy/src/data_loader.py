"""Carga y validación de datos OHLCV (CSV o parquet).

Salida común: índice DatetimeIndex en UTC (inicio de la vela), columnas open, high, low, close, volume y, si existe,
instrument_id. Nunca se inventan ni rellenan datos: las filas inválidas se eliminan y se informan; si la calidad es
insuficiente se lanza DataQualityError y el backtest no continúa.
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNAS = ["open", "high", "low", "close", "volume"]
NOMBRES_TIEMPO = ("timestamp", "datetime", "date_time", "time", "date", "ts_event")


class DataQualityError(Exception):
    """Datos ausentes o de calidad insuficiente: el backtest se detiene."""


def _archivos(ruta: str, base: Path) -> list[Path]:
    patron = str((base / ruta) if not Path(ruta).is_absolute() else Path(ruta))
    return [Path(p) for p in sorted(glob.glob(patron))]


def _normalizar(df: pd.DataFrame, tz_si_naive: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not isinstance(df.index, pd.DatetimeIndex):
        col = next((c for c in NOMBRES_TIEMPO if c in df.columns), None)
        if col is None:
            raise DataQualityError(f"No hay columna de tiempo (se buscó {NOMBRES_TIEMPO}).")
        df.index = pd.to_datetime(df.pop(col), utc=False)
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise DataQualityError(f"Faltan columnas obligatorias: {faltan}.")
    idx = df.index
    idx = idx.tz_localize(tz_si_naive) if idx.tz is None else idx
    df.index = idx.tz_convert("UTC")
    df.index.name = "timestamp"
    cols = COLUMNAS + (["instrument_id"] if "instrument_id" in df.columns else [])
    df = df[cols]
    for c in COLUMNAS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.sort_index(kind="stable")


def load_ohlcv(ruta: str, base: Path, tz_si_naive: str = "UTC") -> pd.DataFrame:
    archivos = _archivos(ruta, base)
    if not archivos:
        raise DataQualityError(f"No se encontraron datos en '{ruta}' (relativo a {base}). Ver data/README.md.")
    partes = []
    for f in archivos:
        if f.suffix == ".parquet":
            partes.append(pd.read_parquet(f))
        elif f.suffix in (".csv", ".txt"):
            partes.append(pd.read_csv(f))
        else:
            raise DataQualityError(f"Formato no soportado: {f.name}")
    return _normalizar(pd.concat(partes), tz_si_naive)


def validate_and_clean(df: pd.DataFrame, source_minutes: int, max_invalid_fraction: float) -> tuple[pd.DataFrame, dict]:
    """Elimina duplicados (se queda con la última) y filas inválidas; devuelve (datos limpios, informe)."""
    n0 = len(df)
    if n0 == 0:
        raise DataQualityError("El fichero de datos está vacío.")
    dup = df.index.duplicated(keep="last")
    df = df[~dup]
    nan = df[COLUMNAS].isna().any(axis=1)
    o, h, l, c, v = (df[k] for k in COLUMNAS)
    ohlc_mal = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l) | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    vol_neg = v < 0
    invalidas = nan | ohlc_mal | vol_neg
    desalineadas = (df.index.second != 0) | ((df.index.minute % source_minutes) != 0 if source_minutes > 1 else False)
    informe = {
        "filas_leidas": n0, "duplicadas_eliminadas": int(dup.sum()), "filas_con_nan": int(nan.sum()),
        "ohlc_inconsistente": int((ohlc_mal & ~nan).sum()), "volumen_negativo": int(vol_neg.sum()),
        "volumen_cero": int((v == 0).sum()), "timestamps_desalineados": int(np.asarray(desalineadas).sum()),
        "primera": str(df.index.min()), "ultima": str(df.index.max()),
        "contratos_distintos": int(df.instrument_id.nunique()) if "instrument_id" in df else None,
    }
    frac = invalidas.sum() / max(len(df), 1)
    informe["filas_invalidas_eliminadas"] = int(invalidas.sum())
    informe["fraccion_invalida"] = float(frac)
    if frac > max_invalid_fraction:
        raise DataQualityError(f"{frac:.4%} de filas inválidas (máximo {max_invalid_fraction:.4%}). Revisa la fuente.")
    limpio = df[~invalidas]
    informe["filas_validas"] = len(limpio)
    return limpio, informe
