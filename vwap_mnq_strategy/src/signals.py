"""Señales y filtros. Todo se evalúa al CIERRE de la vela de 15 min k con datos <= k; la ejecución es en la
apertura de la vela k+1 (la hace el backtester).

Señal base (VWAP direccional):
  lado_k = +1 si cierre > VWAP, -1 si cierre < VWAP, 0 si coincide (no genera señal).
  A) cruce  : señal +1 en k si lado_k = +1 y el último lado no nulo anterior (misma sesión) era -1.
  B) confirm: señal +1 en k si lado_k = lado_{k-1} = +1 y en k-1 hubo cruce (la primera vela cerrada que
              CONFIRMA el lado tras cruzar). Simétrico para -1. La primera vela de la sesión nunca da señal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


def lado(close, vwap) -> np.ndarray:
    d = np.asarray(close, float) - np.asarray(vwap, float)
    out = np.sign(d)
    out[~np.isfinite(d)] = 0
    return out.astype(int)


def señales(bars: pd.DataFrame, vwap_col: str, modo: str) -> np.ndarray:
    lad = pd.Series(lado(bars.close, bars[vwap_col]), index=bars.index)
    ses = bars.session.to_numpy()
    no_nulo = lad.replace(0, np.nan)
    ultimo_prev = no_nulo.groupby(ses).ffill().groupby(ses).shift(1)       # último lado no nulo ANTES de k
    cruce = ((lad != 0) & (ultimo_prev == -lad)).to_numpy()
    if modo == "cross":
        sig = np.where(cruce, lad.to_numpy(), 0)
    elif modo == "confirm":
        lad_prev = lad.groupby(ses).shift(1)
        cruce_prev = pd.Series(cruce).groupby(ses).shift(1).fillna(False).astype(bool).to_numpy()
        ok = (lad != 0).to_numpy() & (lad_prev.to_numpy() == lad.to_numpy()) & cruce_prev
        sig = np.where(ok, lad.to_numpy(), 0)
    else:
        raise ValueError(f"entry_mode desconocido: {modo}")
    return sig.astype(int)


# ------------------------------------------------------------------------------------------------ indicadores
def añadir_indicadores(bars: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """ATR/EMA/RSI por tramo de contrato; pendiente del VWAP por sesión; rango inicial por sesión."""
    b = bars.copy()
    f = cfg["strategy"]["filters"]
    seg, ses = b.segment.to_numpy(), b.session.to_numpy()
    vw = b[cfg["_vwap_col"]].to_numpy()
    b["vwap"] = vw
    b["atr"] = ind.atr(b.high, b.low, b.close, cfg["strategy"]["atr_period"], seg)
    b["ema"] = ind.ema(b.close, f["ema"]["period"], seg)
    b["rsi"] = ind.rsi(b.close, f["rsi"]["period"], seg)
    b["vwap_slope"] = ind.slope(vw, f["vwap_slope"]["bars"], ses)
    # Régimen de ATR: percentil del ATR actual frente a las `lookback_bars` velas ANTERIORES (sin la actual)
    lb = f["atr_regime"]["lookback_bars"]
    atr_s = pd.Series(b.atr)
    b["atr_pct_rank"] = atr_s.rolling(lb + 1, min_periods=lb // 2).apply(
        lambda w: (w[:-1] < w[-1]).mean() * 100 if np.isfinite(w[-1]) else np.nan, raw=True).to_numpy()
    # Rango inicial de los primeros N minutos y su mediana en las sesiones anteriores
    ir_min = f["initial_range"]["minutes"]
    nb = max(1, ir_min // cfg["bars"]["minutes"])
    prim = b[b.k < nb].groupby("session").agg(h=("high", "max"), l=("low", "min"))
    ir = (prim.h - prim.l)
    med = ir.shift(1).rolling(f["initial_range"]["lookback_sessions"], min_periods=10).median()
    b["ir"] = b.session.map(ir)
    b["ir_rel"] = b.session.map(ir / med)
    b["ir_ready"] = b.k >= nb - 1                     # el rango inicial se conoce al cierre de la vela nb-1
    return b


# --------------------------------------------------------------------------------------------------- filtros
def filtros(b: pd.DataFrame, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (permite_largo, permite_corto) al cierre de cada vela. Los filtros desactivados no restringen."""
    f = cfg["strategy"]["filters"]
    n = len(b)
    L, S = np.ones(n, bool), np.ones(n, bool)
    c = b.close.to_numpy()
    if f["vwap_slope"]["enabled"]:
        sl = b.vwap_slope.to_numpy()
        L &= sl > 0
        S &= sl < 0
    if f["ema"]["enabled"]:
        e = b.ema.to_numpy()
        L &= c > e
        S &= c < e
    if f["atr_regime"]["enabled"]:
        r = b.atr_pct_rank.to_numpy()
        ok = (r >= f["atr_regime"]["low_pct"]) & (r <= f["atr_regime"]["high_pct"])
        L &= ok
        S &= ok
    if f["rsi"]["enabled"]:
        r = b.rsi.to_numpy()
        L &= r > f["rsi"]["level"]
        S &= r < f["rsi"]["level"]
    if f["initial_range"]["enabled"]:
        ok = b.ir_ready.to_numpy() & (b.ir_rel.to_numpy() <= 1.0)    # hipótesis fijada: días de apertura estrecha
        L &= ok
        S &= ok
    if f["vwap_distance"]["enabled"]:
        dist = np.abs(c - b.vwap.to_numpy()) / b.atr.to_numpy()
        ok = (dist >= f["vwap_distance"]["min_atr"]) & (dist <= f["vwap_distance"]["max_atr"])
        L &= ok
        S &= ok
    L &= np.isfinite(c)
    S &= np.isfinite(c)
    return L, S


def ventana_horaria(cfg: dict):
    """(inicio, fin) en minutos NY para la vela de ENTRADA si el filtro horario está activo; si no, None."""
    w = cfg["strategy"]["filters"]["time_window"]
    if not w["enabled"]:
        return None
    h0, m0 = map(int, w["start"].split(":"))
    h1, m1 = map(int, w["end"].split(":"))
    return h0 * 60 + m0, h1 * 60 + m1
