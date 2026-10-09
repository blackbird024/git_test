"""Indicadores diarios conocidos ANTES de cada sesión (todo desplazado un día: sin información futura)."""
import numpy as np
import pandas as pd


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def atr(d: pd.DataFrame, n=14) -> pd.Series:
    pc = d["close"].shift(1)
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def daily_context(daily: pd.DataFrame) -> dict:
    """{fecha: dict} con valores del día ANTERIOR: cierre, ATR14, EMA50, EMA200, percentil de volatilidad (1 año)."""
    d = daily.copy()
    f = pd.DataFrame(index=d.index)
    f["prev_close"] = d["close"]
    f["prev_high"] = d["high"]
    f["prev_low"] = d["low"]
    f["atr14"] = atr(d, 14)
    f["ema50"] = ema(d["close"], 50)
    f["ema200"] = ema(d["close"], 200)
    f["atr_pct"] = f["atr14"] / d["close"]
    f["vol_rank"] = f["atr_pct"].rolling(252, min_periods=126).rank(pct=True)
    f = f.shift(1)                                  # ← clave: lo disponible al empezar la sesión
    return {k: r._asdict() for k, r in zip(f.index, f.itertuples(index=False))}
