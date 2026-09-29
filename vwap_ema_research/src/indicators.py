"""Indicadores causales (fila i usa solo filas <= i). `grupo` reinicia el cálculo (sesión o tramo de contrato)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def vwap(high, low, close, volume, grupo) -> np.ndarray:
    tp = (np.asarray(high, float) + np.asarray(low, float) + np.asarray(close, float)) / 3
    vol = np.asarray(volume, float)
    g = np.asarray(grupo)
    pv = pd.Series(tp * vol).groupby(g).cumsum().to_numpy()
    cv = pd.Series(vol).groupby(g).cumsum().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        out = pv / cv
    out[cv <= 0] = np.nan
    return out


def ema(x, n: int, grupo) -> np.ndarray:
    s = pd.Series(np.asarray(x, float))
    return s.groupby(np.asarray(grupo)).transform(lambda v: v.ewm(span=n, adjust=False, min_periods=n).mean()).to_numpy()


def atr(high, low, close, n: int, grupo) -> np.ndarray:
    """ATR = media simple de n rangos verdaderos."""
    h, l, c = (pd.Series(np.asarray(v, float)) for v in (high, low, close))
    g = np.asarray(grupo)
    prev = c.groupby(g).shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.groupby(g).transform(lambda s: s.rolling(n, min_periods=n).mean()).to_numpy()


def slope(x, n: int, grupo) -> np.ndarray:
    s = pd.Series(np.asarray(x, float))
    return (s - s.groupby(np.asarray(grupo)).shift(n)).to_numpy()


def rolling_min(x, n: int, grupo) -> np.ndarray:
    s = pd.Series(np.asarray(x, float))
    return s.groupby(np.asarray(grupo)).transform(lambda v: v.rolling(n, min_periods=1).min()).to_numpy()


def rolling_max(x, n: int, grupo) -> np.ndarray:
    s = pd.Series(np.asarray(x, float))
    return s.groupby(np.asarray(grupo)).transform(lambda v: v.rolling(n, min_periods=1).max()).to_numpy()
