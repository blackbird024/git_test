"""BOT 16 — MOMENTUM BREAKOUT (NQ, velas de 5 min, entradas 09:45-15:30 NY).

Hipótesis: una expansión repentina de volatilidad acompañada de ruptura continúa durante cierto tiempo.

Reglas (base, 3 reglas):
  1. Expansión: rango de la vela > m × ATR(20) de las velas ANTERIORES (m = 1,25).
  2. Ruptura: cierre por encima del máximo (o por debajo del mínimo) de las N velas anteriores (N = 10).
  3. Stop 1 × ATR(20); salida por tiempo 60 min después de la entrada (o 15:55).
De una en una: N 5/20, m 1,0/1,5, salida 2R, trailing 1,5 ATR, 30 min, filtro de volumen relativo > 1,5.
"""
from __future__ import annotations

import numpy as np

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

BOT = "16"
NOMBRE = "Momentum breakout"
HIPOTESIS = "Una expansión repentina de volatilidad con ruptura del rango reciente continúa durante cierto tiempo."
MARCO, SESION, FRECUENCIA = "5m", "NY 09:45-15:30", "intradia"

_B = dict(n=10, m=1.25, salida="tiempo", minutos=60, filtro_vol=None)
VARIANTES = {
    "16.01 base N10 m1.25 stop 1 ATR, 60 min": _B,
    "16.02 N5": {**_B, "n": 5},
    "16.03 N20": {**_B, "n": 20},
    "16.04 m1.0": {**_B, "m": 1.0},
    "16.05 m1.5": {**_B, "m": 1.5},
    "16.06 salida 2R": {**_B, "salida": "2R"},
    "16.07 trailing 1.5 ATR": {**_B, "salida": "trailing"},
    "16.08 salida 30 min": {**_B, "minutos": 30},
    "16.09 + volumen relativo > 1.5": {**_B, "filtro_vol": 1.5},
}
BASE = "16.01 base N10 m1.25 stop 1 ATR, 60 min"


def vecindad(p: dict) -> dict:
    n, m = p["n"], p["m"]
    out = {f"n={x}": {**p, "n": x} for x in (max(3, int(round(n * 0.8))), int(round(n * 1.2)))}
    out.update({f"m={x}": {**p, "m": x} for x in (round(m * 0.9, 3), round(m * 1.1, 3))})
    if p["salida"] == "tiempo":
        out.update({f"min={x}": {**p, "minutos": x} for x in (int(p["minutos"] * 0.75), int(p["minutos"] * 1.25))})
    return out


def ordenes(ctx, p: dict):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    atr_prev = np.r_[np.nan, d["atr20"][:-1]]
    expansion = (v.H - v.L) > p["m"] * atr_prev
    hi, lo = ind.maximo_previo(v.Ha, p["n"]), ind.minimo_previo(v.La, p["n"])
    ok = B.ventana(v, 585, 930) & np.isfinite(atr_prev) & expansion
    if p["filtro_vol"] is not None:
        rv = B.cache(ctx, "relvol5", lambda: ind.volumen_relativo_hora(v.V, v.fecha, v.min_ny))
        ok &= rv > p["filtro_vol"]
    largo = ok & (v.Ca > hi)
    corto = ok & (v.Ca < lo)
    sel = np.flatnonzero(largo | corto)
    i_sig = v.i1[sel]
    eod = B.fin_por_tiempo(ctx, v, sel)
    cols = dict(i_sig=i_sig, dir=np.where(largo[sel], 1, -1), stop_dist=atr_prev[sel])
    if p["salida"] == "tiempo":
        cols["i_fin"] = B.fin_tras_minutos(ctx, i_sig, p["minutos"], eod)
    else:
        cols["i_fin"] = eod
        if p["salida"] == "2R":
            cols["r_obj"] = 2.0
        else:
            cols["trail"] = 1.5 * atr_prev[sel]
    return B.df_ordenes(**cols)


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult)
