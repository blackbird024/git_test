"""Indicadores. Todos son causales: el valor en la fila i solo usa filas <= i.

`grupo` reinicia el cálculo (sesión para el VWAP; tramo de contrato para ATR/EMA/RSI, para que un cambio de
vencimiento no contamine los indicadores con el salto de precio entre contratos).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def typical_price(high, low, close):
    return (np.asarray(high, float) + np.asarray(low, float) + np.asarray(close, float)) / 3.0


def vwap(high, low, close, volume, grupo) -> np.ndarray:
    """VWAP acumulado desde el inicio de cada grupo (sesión): sum(tp*vol) / sum(vol). NaN mientras el volumen
    acumulado sea 0."""
    tp = typical_price(high, low, close)
    vol = np.asarray(volume, float)
    g = pd.Series(np.asarray(grupo))
    pv = pd.Series(tp * vol).groupby(g.values).cumsum().to_numpy()
    cv = pd.Series(vol).groupby(g.values).cumsum().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        out = pv / cv
    out[cv <= 0] = np.nan
    return out


def vwap_std(high, low, close, volume, grupo) -> np.ndarray:
    """Desviación típica ponderada por volumen del precio típico respecto al VWAP (para bandas)."""
    tp = typical_price(high, low, close)
    vol = np.asarray(volume, float)
    g = np.asarray(grupo)
    cv = pd.Series(vol).groupby(g).cumsum().to_numpy()
    m1 = pd.Series(tp * vol).groupby(g).cumsum().to_numpy()
    m2 = pd.Series(tp * tp * vol).groupby(g).cumsum().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        media = m1 / cv
        var = np.maximum(m2 / cv - media ** 2, 0.0)
    var[cv <= 0] = np.nan
    return np.sqrt(var)


def true_range(high, low, close, grupo) -> np.ndarray:
    h, l, c = (pd.Series(np.asarray(x, float)) for x in (high, low, close))
    prev = c.groupby(np.asarray(grupo)).shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.to_numpy()


def atr(high, low, close, n: int, grupo) -> np.ndarray:
    """ATR como media simple de n rangos verdaderos (documentado: SMA, no Wilder)."""
    tr = pd.Series(true_range(high, low, close, grupo))
    return tr.groupby(np.asarray(grupo)).transform(lambda s: s.rolling(n, min_periods=n).mean()).to_numpy()


def ema(x, n: int, grupo) -> np.ndarray:
    s = pd.Series(np.asarray(x, float))
    return s.groupby(np.asarray(grupo)).transform(lambda v: v.ewm(span=n, adjust=False, min_periods=n).mean()).to_numpy()


def rsi(close, n: int, grupo) -> np.ndarray:
    """RSI de Wilder."""
    c = pd.Series(np.asarray(close, float))
    g = np.asarray(grupo)

    def _rsi(v: pd.Series) -> pd.Series:
        d = v.diff()
        sube = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        baja = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        return 100 - 100 / (1 + sube / baja.replace(0, np.nan))

    return c.groupby(g).transform(_rsi).to_numpy()


def slope(x, n: int, grupo) -> np.ndarray:
    """x[i] - x[i-n] dentro del mismo grupo (NaN si cruza de grupo)."""
    s = pd.Series(np.asarray(x, float))
    return (s - s.groupby(np.asarray(grupo)).shift(n)).to_numpy()
