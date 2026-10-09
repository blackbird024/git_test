"""Sistema B · swing diario sobre el Nasdaq-100 (QQQ ajustado como proxy). Solo largos, sin apalancamiento.

Todas las señales se calculan con el cierre del día t usando solo datos hasta t (las ventanas de máximos excluyen el
propio día). Cada función devuelve un DataFrame con: entry (bool), exit (bool), stop_dist (distancia del stop inicial
en precio, NaN = sin stop), max_days (salida por tiempo, None = sin límite).

B1  ruptura de 20 sesiones: cierre > máximo de los 20 días anteriores. Stop 2×ATR20. Sale con cierre < mínimo de los
    10 días anteriores (ruptura contraria) o a los 20 días de mercado (~4 semanas).
B2  B1 + filtro: (a) cierre > EMA200, (b) EMA200 con pendiente positiva (vs. 20 días antes), (c) volatilidad
    (ATR20/precio) por debajo de su mediana de 1 año.
B3  RSI(2) de Connors (reversión a la media, se clasifica aparte): RSI(2) < 10 y cierre > SMA200 → compra;
    cierre > SMA5 → vende. Sin stop y sin límite de tiempo (reglas originales de alpaca/swing_lab.py).
B4  retroceso en tendencia: cierre > EMA200 y EMA20 > EMA50; el mínimo toca la EMA20 y el cierre queda por encima.
    Stop 2×ATR20. Sale con cierre < EMA50 o a los 20 días.
"""
import numpy as np
import pandas as pd


def ema(x, n):
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def atr(d, n=20):
    pc = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(c, n=2):
    """RSI de Wilder (la misma fórmula que alpaca/strategy_lab.py)."""
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def _out(d, entry, exit_, stop_dist, max_days):
    return pd.DataFrame({"entry": entry.fillna(False), "exit": exit_.fillna(False), "stop_dist": stop_dist,
                         "max_days": max_days}, index=d.index)


def breakout20(d, filt=None, n_hi=20, n_lo=10, atr_mult=2.0, max_days=20):
    c = d["close"]
    hi = d["high"].rolling(n_hi).max().shift(1)
    lo = d["low"].rolling(n_lo).min().shift(1)
    a = atr(d)
    entry = c > hi
    if filt == "ema200":
        entry &= c > ema(c, 200)
    elif filt == "pendiente":
        e = ema(c, 200)
        entry &= e > e.shift(20)
    elif filt == "vol":
        v = a / c
        entry &= v < v.rolling(252, min_periods=126).median()
    return _out(d, entry, c < lo, atr_mult * a, max_days)


def rsi2(d, lo=10):
    c = d["close"]
    return _out(d, (rsi(c, 2) < lo) & (c > c.rolling(200).mean()), c > c.rolling(5).mean(),
                pd.Series(np.nan, index=d.index), None)


def pullback_ema20(d, atr_mult=2.0, max_days=20):
    c = d["close"]
    e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    entry = (c > e200) & (e20 > e50) & (d["low"] <= e20) & (c > e20)
    return _out(d, entry, c < e50, atr_mult * atr(d), max_days)


SWING = {
    "B1 Ruptura 20 sesiones": (breakout20, {}),
    "B2 Ruptura 20 + EMA200": (breakout20, dict(filt="ema200")),
    "B2 Ruptura 20 + pendiente EMA200": (breakout20, dict(filt="pendiente")),
    "B2 Ruptura 20 + volatilidad baja": (breakout20, dict(filt="vol")),
    "B3 RSI(2) Connors (reversión)": (rsi2, {}),
    "B4 Retroceso a EMA20 en tendencia": (pullback_ema20, {}),
}
