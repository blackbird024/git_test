"""Variables, modelos A-D, tipos de entrada y señales de salida. Todo al CIERRE de la vela k con datos <= k.

MODELOS (condición de dirección):
  A  largo: cierre > VWAP                                   corto: cierre < VWAP
  B  A y cierre > EMA200                                   (corto: cierre < EMA200)
  C  A y EMA50 > EMA200 y cierre > EMA200                   (simétrico)
  D  C y cierre > EMA20 (EMA20 solo como filtro de timing)  (simétrico)
ENTRADAS:
  state    : la condición del modelo se cumple al cierre (se entra si no hay posición).
  breakout : el cierre CRUZA el VWAP (el último cierre no igual al VWAP estaba al otro lado, misma sesión), la vela
             confirma (cierre > apertura en largos) y el resto de condiciones del modelo se cumplen.
  pullback : la vela anterior cerró por encima del VWAP; la vela actual retrocede (mínimo <= max(VWAP, EMA20)),
             cierra por encima del VWAP y alcista (cierre > apertura); condiciones del modelo cumplidas. Simétrico.
FILTROS DE TENDENCIA (independientes): ema200_slope (pendiente de la EMA200 a favor), vwap_slope (pendiente del VWAP).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


def features(b: pd.DataFrame, p: dict) -> pd.DataFrame:
    x = b.copy()
    seg, ses = x.segment.to_numpy(), x.session.to_numpy()
    for nombre, n in (("ema_fast", p["ema_fast"]), ("ema_medium", p["ema_medium"]), ("ema_slow", p["ema_slow"])):
        x[nombre] = ind.ema(x.close, n, seg)                   # continua entre sesiones, reiniciada en cada contrato
    x["atr"] = ind.atr(x.high, x.low, x.close, p["atr_period"], seg)
    x["vwap_dist"] = x.close - x.vwap
    x["vwap_dist_pct"] = x.vwap_dist / x.vwap * 100
    x["vwap_slope"] = ind.slope(x.vwap, p["slope_bars"], ses)
    x["ema_slow_slope"] = ind.slope(x.ema_slow, p["slope_bars"], seg)
    x["struct_low"] = ind.rolling_min(x.low, p["structure_bars"], ses)
    x["struct_high"] = ind.rolling_max(x.high, p["structure_bars"], ses)
    return x


def model_conditions(x: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    c, v = x.close.to_numpy(), x.vwap.to_numpy()
    e20, e50, e200 = x.ema_fast.to_numpy(), x.ema_medium.to_numpy(), x.ema_slow.to_numpy()
    L, S = c > v, c < v
    if model in ("B", "C", "D"):
        L, S = L & (c > e200), S & (c < e200)
    if model in ("C", "D"):
        L, S = L & (e50 > e200), S & (e50 < e200)
    if model == "D":
        L, S = L & (c > e20), S & (c < e20)
    if model not in ("A", "B", "C", "D"):
        raise ValueError(model)
    return L, S


def trend_filters(x: pd.DataFrame, filtros: list[str]) -> tuple[np.ndarray, np.ndarray]:
    n = len(x)
    L, S = np.ones(n, bool), np.ones(n, bool)
    for f in filtros:
        col = {"ema200_slope": "ema_slow_slope", "vwap_slope": "vwap_slope"}[f]
        s = x[col].to_numpy()
        L &= s > 0
        S &= s < 0
    return L, S


def entry_signals(x: pd.DataFrame, p: dict) -> np.ndarray:
    L, S = model_conditions(x, p["model"])
    fl, fs = trend_filters(x, p["trend_filters"])
    L, S = L & fl, S & fs
    c, o, lo, hi = (x[k].to_numpy() for k in ("close", "open", "low", "high"))
    v, e20 = x.vwap.to_numpy(), x.ema_fast.to_numpy()
    ses = x.session.to_numpy()
    et = p["entry_type"]
    if et == "state":
        pass
    elif et == "breakout":
        lado = pd.Series(np.sign(c - v)).replace(0, np.nan)
        prev = lado.groupby(ses).ffill().groupby(ses).shift(1).to_numpy()
        L &= (prev == -1) & (c > o)
        S &= (prev == 1) & (c < o)
    elif et == "pullback":
        prev_c = pd.Series(c).groupby(ses).shift(1).to_numpy()
        prev_v = pd.Series(v).groupby(ses).shift(1).to_numpy()
        L &= (prev_c > prev_v) & (lo <= np.fmax(v, e20)) & (c > o)
        S &= (prev_c < prev_v) & (hi >= np.fmin(v, e20)) & (c < o)
    else:
        raise ValueError(et)
    sig = np.zeros(len(x), int)
    sig[L & ~S] = 1
    sig[S & ~L] = -1
    return sig


def exit_signals(x: pd.DataFrame, exit_type: str) -> tuple[np.ndarray, np.ndarray]:
    """(salir_largo, salir_corto) al cierre de la vela, para las salidas por señal."""
    c = x.close.to_numpy()
    n = len(x)
    if exit_type == "vwap":
        v = x.vwap.to_numpy()
        return c < v, c > v
    if exit_type == "ema20":
        e = x.ema_fast.to_numpy()
        return c < e, c > e
    return np.zeros(n, bool), np.zeros(n, bool)
