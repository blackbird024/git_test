"""Marcos temporales superiores (5M, 1H, 4H, 1D) a partir del 1M.

  - 5M y 1H: bloques de reloj en UTC (9:30, 9:35... / 10:00, 11:00...).
  - 4H y 1D: alineados con la sesión de CME, que empieza a las 18:00 de Nueva York. Así la vela diaria es
    la sesión de futuros completa y el cambio de horario de EE. UU. no la parte en dos.

Cada vela lleva la columna `disponible_utc`: el instante en que la vela está CERRADA (último minuto + 1).
Una estrategia solo puede usar una vela de marco superior a partir de ese instante; así se evita
el look-ahead al mezclar marcos.
"""
import pandas as pd

from src.horas import NUEVA_YORK, UTC

AGREGAR = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def remuestrear(m1: pd.DataFrame, marco: str) -> pd.DataFrame:
    if marco in ("5M", "1H"):
        clave = m1.index.floor("5min" if marco == "5M" else "1h")
    elif marco in ("4H", "1D"):
        ny = m1.index.tz_convert(NUEVA_YORK).tz_localize(None) + pd.Timedelta(hours=6)  # sesión = día natural
        bloque = ny.floor("4h") if marco == "4H" else ny.normalize()
        inicio_ny = (bloque - pd.Timedelta(hours=6))
        clave = inicio_ny.tz_localize(NUEVA_YORK, ambiguous="NaT", nonexistent="shift_forward").tz_convert(UTC)
    else:
        raise ValueError("marco debe ser 5M, 1H, 4H o 1D")
    cols = {k: v for k, v in AGREGAR.items() if k in m1}
    g = m1.groupby(clave)
    out = g.agg(cols)
    out["disponible_utc"] = pd.Series(m1.index, index=m1.index).groupby(clave).max() + pd.Timedelta(minutes=1)
    out.index.name = "inicio_utc"
    return out[out.index.notna()]


def ultima_cerrada(marco_df: pd.DataFrame, instante: pd.Timestamp) -> pd.Series | None:
    """La última vela del marco que ya estaba cerrada en `instante` (o None)."""
    cerradas = marco_df[marco_df.disponible_utc <= instante]
    return None if cerradas.empty else cerradas.iloc[-1]
