"""Proveedor CSV y validación de datos.

Esquema del CSV (una fila por vela, ordenado por tiempo):
    timestamp,open,high,low,close[,volume][,contract]
- timestamp: ISO 8601 CON desplazamiento horario explícito (p. ej. 2024-03-11T09:30:00-04:00 o ...Z). Las marcas sin
  zona horaria se rechazan: con el cambio de hora serían ambiguas.
- La marca es la APERTURA de la vela (timestamp_is: start). Velas de `bar_minutes` minutos.
- Precios numéricos en puntos del índice (no en USD por contrato). volume y contract son opcionales.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class DataError(ValueError):
    pass


@dataclass
class Validation:
    rows: int = 0
    first: str = ""
    last: str = ""
    duplicates: int = 0
    out_of_order: int = 0
    impossible_ohlc: int = 0
    non_positive: int = 0
    off_grid_prices: int = 0
    misaligned_timestamps: int = 0
    suspicious_jumps: int = 0
    bars_outside_rth: int = 0
    rth_sessions: int = 0
    rth_sessions_with_missing_bars: int = 0
    rth_missing_bars: int = 0
    fatal: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.fatal


def read_csv(path, tz="America/New_York") -> pd.DataFrame:
    try:
        raw = pd.read_csv(path, dtype={"timestamp": str})
    except FileNotFoundError as e:
        raise DataError(f"no existe el archivo de datos {path}") from e
    need = {"timestamp", "open", "high", "low", "close"}
    miss = need - set(raw.columns)
    if miss:
        raise DataError(f"faltan columnas obligatorias: {sorted(miss)}")
    ts = raw["timestamp"].astype(str)
    has_tz = ts.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    if not has_tz.all():
        raise DataError(f"{(~has_tz).sum()} marcas de tiempo sin zona horaria explícita (ambiguas); "
                        f"primera: {ts[~has_tz].iloc[0]!r}")
    try:
        idx = pd.to_datetime(ts, utc=True, format="ISO8601").dt.tz_convert(tz)
    except Exception as e:  # noqa: BLE001
        raise DataError(f"marcas de tiempo no interpretables: {e}") from e
    df = raw.drop(columns=["timestamp"]).copy()
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["open", "high", "low", "close"]].isna().any().any():
        n = int(df[["open", "high", "low", "close"]].isna().any(axis=1).sum())
        raise DataError(f"{n} filas con precios no numéricos o vacíos")
    df.index = pd.DatetimeIndex(idx, name="timestamp")
    return df


def validate(df: pd.DataFrame, tick_size: float, bar_minutes: int, rth_start="09:30", rth_end="16:00",
             jump_pct: float = 0.08) -> Validation:
    v = Validation(rows=len(df))
    if len(df) == 0:
        v.fatal.append("dataset vacío")
        return v
    v.first, v.last = str(df.index[0]), str(df.index[-1])
    t = df.index
    v.duplicates = int(t.duplicated().sum())
    v.out_of_order = int((np.diff(t.asi8) < 0).sum())
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    v.impossible_ohlc = int(((h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)).sum())
    v.non_positive = int(((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)).sum())
    grid = np.abs(np.stack([o, h, l, c]) / tick_size - np.round(np.stack([o, h, l, c]) / tick_size))
    v.off_grid_prices = int((grid > 1e-6).any(axis=0).sum())
    v.misaligned_timestamps = int(((t.minute % bar_minutes) != 0).sum() + (t.second != 0).sum())
    ret = np.abs(np.diff(c) / c[:-1]) if len(c) > 1 else np.array([])
    v.suspicious_jumps = int((ret > jump_pct).sum())
    mins = t.hour * 60 + t.minute
    a = int(rth_start[:2]) * 60 + int(rth_start[3:])
    b = int(rth_end[:2]) * 60 + int(rth_end[3:])
    rth = (mins >= a) & (mins < b) & (t.dayofweek < 5)
    v.bars_outside_rth = int((~rth).sum())
    per_day = pd.Series(1, index=t[rth]).groupby(t[rth].date).size()
    expected = (b - a) // bar_minutes
    v.rth_sessions = int(len(per_day))
    short = per_day[per_day < expected]
    v.rth_sessions_with_missing_bars = int(len(short))
    v.rth_missing_bars = int((expected - short).sum())
    if v.duplicates:
        v.fatal.append(f"{v.duplicates} marcas de tiempo duplicadas")
    if v.out_of_order:
        v.fatal.append(f"{v.out_of_order} velas fuera de orden")
    if v.impossible_ohlc:
        v.fatal.append(f"{v.impossible_ohlc} velas con OHLC imposible")
    if v.non_positive:
        v.fatal.append(f"{v.non_positive} velas con precios <= 0")
    if v.misaligned_timestamps:
        v.fatal.append(f"{v.misaligned_timestamps} marcas no alineadas a {bar_minutes} min")
    if v.off_grid_prices:
        v.warnings.append(f"{v.off_grid_prices} velas con precios fuera de la rejilla de {tick_size} (¿escala o ajuste por rollover?)")
    if v.suspicious_jumps:
        v.warnings.append(f"{v.suspicious_jumps} saltos > {jump_pct:.0%} entre velas consecutivas (¿error de escala o rollover?)")
    if v.rth_sessions_with_missing_bars:
        v.warnings.append(f"{v.rth_sessions_with_missing_bars} sesiones regulares incompletas "
                          f"({v.rth_missing_bars} velas ausentes; incluye medias jornadas y festivos con Globex abierto)")
    return v
