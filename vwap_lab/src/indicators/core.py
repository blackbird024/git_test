"""Indicadores. Todos usan solo información hasta la vela evaluada (incluida, ya cerrada).

- EMA(n): media exponencial de cierres de 5 min con alpha = 2/(n+1), recursiva desde la primera vela de la serie
  (no se reinicia por sesión). Las primeras ~3n velas de la serie están poco inicializadas: los datos empiezan en 2018 y
  la primera sesión evaluada está varias semanas después.
- ATR(14): media de Wilder (alpha = 1/14) del rango verdadero (usa el cierre anterior), continua en toda la serie.
- VWAP de sesión: acumulado de precio típico × volumen desde la vela de inicio de la sesión, reiniciado cada sesión.
- Pendiente del VWAP en la vela t = (VWAP[t] − VWAP[t−6]) / ATR14[t], solo si t−6 pertenece a la misma sesión; si no, NaN.
"""
import numpy as np
import pandas as pd


def ema(close: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(close).ewm(span=n, adjust=False).mean().to_numpy()


def atr(high, low, close, n=14) -> np.ndarray:
    pc = np.r_[np.nan, close[:-1]]
    tr = np.nanmax(np.vstack([high - low, np.abs(high - pc), np.abs(low - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def session_vwap(high, low, close, volume) -> np.ndarray:
    tp = (high + low + close) / 3
    cv = np.cumsum(volume)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.cumsum(tp * volume) / cv


def vwap_slope(vwap: np.ndarray, atr_: np.ndarray, k=6) -> np.ndarray:
    out = np.full(len(vwap), np.nan)
    if len(vwap) > k:
        out[k:] = (vwap[k:] - vwap[:-k]) / atr_[k:]
    return out


def rsi(close: np.ndarray, n=14) -> np.ndarray:
    """RSI de Wilder sobre cierres de 5 min, continuo en toda la serie (solo usa cierres pasados y el actual)."""
    d = np.diff(close, prepend=close[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn == 0, 100.0, 100 - 100 / (1 + up / dn))
