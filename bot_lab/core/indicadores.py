"""Indicadores causales (el valor en la posición i solo usa datos hasta i). Se aplican a precios AJUSTADOS por cambio
de contrato (ver core/datos.py) salvo que se diga otra cosa."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(x: np.ndarray, n: int) -> np.ndarray:
    """EMA estándar (alfa = 2/(n+1)); NaN hasta tener n valores."""
    s = pd.Series(x).ewm(span=n, adjust=False, min_periods=n).mean()
    return s.to_numpy()


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).mean().to_numpy()


def rango_verdadero(h, l, c) -> np.ndarray:
    cp = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - cp), np.abs(l - cp)]), axis=0)
    return tr


def atr(h, l, c, n: int = 14) -> np.ndarray:
    """ATR de Wilder."""
    tr = rango_verdadero(h, l, c)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def adx(h, l, c, n: int = 14):
    """(ADX, +DI, -DI) de Wilder."""
    up = np.r_[np.nan, h[1:] - h[:-1]]
    dn = np.r_[np.nan, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = rango_verdadero(h, l, c)
    w = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()  # noqa: E731
    atr_ = w(tr)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100 * w(pdm) / atr_
        mdi = 100 * w(mdm) / atr_
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return w(np.nan_to_num(dx, nan=0.0)), pdi, mdi


def rsi(c: np.ndarray, n: int = 2) -> np.ndarray:
    """RSI de Wilder (mismo cálculo que src/strategies/nq_rsi2.rsi)."""
    s = pd.Series(c)
    delta = s.diff()
    sube = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    baja = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    v = 100 - 100 / (1 + sube / baja.where(baja > 0))
    return v.where(baja > 0, 100.0).where(delta.notna().cumsum() > 0).to_numpy()


def maximo_previo(x: np.ndarray, n: int) -> np.ndarray:
    """Máximo de las n posiciones ANTERIORES (sin incluir la actual)."""
    return pd.Series(x).rolling(n).max().shift(1).to_numpy()


def minimo_previo(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).min().shift(1).to_numpy()


def eficiencia_sesion(c: np.ndarray, grupo: np.ndarray) -> np.ndarray:
    """Ratio de eficiencia de Kaufman desde el inicio del grupo (sesión) hasta i: |c_i - c_0| / suma |Δc|."""
    g = pd.Series(grupo)
    s = pd.Series(c)
    c0 = s.groupby(g).transform("first")
    paso = s.groupby(g).diff().abs().fillna(0.0)
    camino = paso.groupby(g).cumsum()
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(camino > 0, (s - c0).abs() / camino, np.nan)


def primero_por_grupo(mascara: np.ndarray, grupo: np.ndarray) -> np.ndarray:
    """True solo en la primera posición de cada grupo donde la máscara es True."""
    m = pd.Series(mascara.astype(bool))
    previo = m.groupby(pd.Series(grupo)).cumsum()
    return (m & (previo == 1)).to_numpy()


def volumen_relativo_hora(v: np.ndarray, fecha: np.ndarray, minuto: np.ndarray, n: int = 20) -> np.ndarray:
    """Volumen / media del volumen de la MISMA vela horaria en las n sesiones anteriores."""
    df = pd.DataFrame({"v": v, "f": fecha, "m": minuto})
    media = df.groupby("m").v.transform(lambda s: s.rolling(n, min_periods=5).mean().shift(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return (df.v / media).to_numpy()
