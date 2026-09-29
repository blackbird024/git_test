"""Acceso a los datos procesados, al corte desarrollo / fuera de muestra y a los días excluidos."""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.calidad import dias_iliquidos
from src.horas import sesion_cme

RAIZ = Path(__file__).resolve().parent.parent.parent
PROCESADOS = RAIZ / "data" / "processed"


@lru_cache(maxsize=None)
def velas_1m(raiz: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESADOS / f"{raiz}_1M.parquet")


def inicio_fuera_de_muestra(raiz: str) -> pd.Timestamp:
    """Primera sesión del periodo fuera de muestra (fijada en config/particion.json)."""
    p = json.loads((RAIZ / "config" / "particion.json").read_text())
    return pd.Timestamp(p[raiz]["inicio_fuera_de_muestra"])


@lru_cache(maxsize=None)
def excluidos(raiz: str) -> frozenset:
    return frozenset(dias_iliquidos(velas_1m(raiz)))


def sesiones(m1: pd.DataFrame) -> pd.DataFrame:
    """Una fila por sesión de CME: apertura, máximo, mínimo, cierre, contrato y hora de la última vela.
    Incluye cierres AJUSTADOS por los cambios de contrato (para indicadores sin saltos de roll):
    el día del cambio se usa cierre/apertura del contrato nuevo en lugar de cierre/cierre anterior."""
    s = sesion_cme(m1.index)
    g = m1.groupby(s)
    d = pd.DataFrame({
        "open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
        "primer_id": g.instrument_id.first(), "ultimo_id": g.instrument_id.last(),
        "t_primera": pd.Series(m1.index, index=m1.index).groupby(s).min(),
        "t_ultima": pd.Series(m1.index, index=m1.index).groupby(s).max(),
        "open_ultima": g.open.last(),       # apertura del último minuto de la sesión (≈ precio de cierre)
    })
    d.index = pd.to_datetime(d.index)
    d.index.name = "sesion"
    return ajustar(d)


def ajustar(d: pd.DataFrame) -> pd.DataFrame:
    """Añade rendimientos y precios ajustados por cambios de contrato (necesita open, close, primer_id, ultimo_id)."""
    d = d.copy()
    mismo = d.primer_id == d.ultimo_id.shift()
    r = np.where(mismo, d.close / d.close.shift() - 1, d.close / d.open - 1)
    r[0] = 0.0
    d["ret"] = r
    d["close_aj"] = d.close.iloc[0] * np.cumprod(1 + d.ret)      # solo usa el pasado
    d["open_aj"] = d.close_aj * d.open / d.close
    return d


def sesiones_diarias_databento(raiz: str) -> pd.DataFrame:
    """Velas diarias de Databento (día natural en UTC) con el mismo formato que `sesiones`."""
    df = pd.read_parquet(RAIZ / "data" / "raw" / "daily" / f"{raiz}.parquet")
    df.index = pd.to_datetime(df.index).tz_convert("UTC")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    d = pd.DataFrame({"open": df.open, "high": df.high, "low": df.low, "close": df.close,
                      "primer_id": df.instrument_id, "ultimo_id": df.instrument_id,
                      "t_primera": df.index, "t_ultima": df.index + pd.Timedelta(hours=23, minutes=59),
                      "open_ultima": df.close})
    d.index = df.index.tz_localize(None).normalize()
    d.index.name = "sesion"
    return ajustar(d)
