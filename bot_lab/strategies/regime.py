"""BOT 19 — VWAP + DETECCIÓN DE RÉGIMEN (NQ, velas de 5 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: la reversión al VWAP funciona en mercados laterales pero falla en tendencias fuertes; en tendencia funciona
la continuación a favor del VWAP.

Régimen (causal, con la vela de la señal):
  - ADX(14) de 5 min: TENDENCIA si > 25; RANGO si < 20.
  - Ratio de eficiencia de la sesión RTH hasta la vela (|cierre − cierre de la 1.ª vela de 5 min| / suma de |Δcierre|):
    TENDENCIA si ≥ 0,4; RANGO si ≤ 0,2.
Estrategias:
  - MR: reglas de la base del BOT 13 (banda 1,5 desviaciones, confirmación, objetivo VWAP, stop extremo), solo en RANGO.
  - Tendencia: precio del lado del VWAP en TENDENCIA; la vela toca el VWAP (mínimo ≤ VWAP en largos), cierra a favor
    y por encima del máximo anterior -> entrada; stop extremo de 3 velas ± 1 tick; objetivo 2R.
Controles (no seleccionables): MR solo en TENDENCIA y tendencia solo en RANGO, para medir si el régimen importa.
"""
from __future__ import annotations

import numpy as np

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B
from bot_lab.strategies import vwap_mean_reversion as mr

BOT = "19"
NOMBRE = "VWAP + régimen"
HIPOTESIS = ("La reversión al VWAP funciona en rango y falla en tendencia; en tendencia funciona la continuación a "
             "favor del VWAP.")
MARCO, SESION, FRECUENCIA = "5m", "NY 10:00-15:00 (salida 15:55)", "intradia"

VARIANTES = {
    "19.01 MR solo en RANGO (ADX)": dict(estrategia="mr", medida="adx", regimen="rango"),
    "19.02 MR solo en RANGO (eficiencia)": dict(estrategia="mr", medida="er", regimen="rango"),
    "19.03 Tendencia VWAP solo en TENDENCIA (ADX)": dict(estrategia="tend", medida="adx", regimen="tendencia"),
    "19.04 Tendencia VWAP solo en TENDENCIA (eficiencia)": dict(estrategia="tend", medida="er", regimen="tendencia"),
    "19.05 control: MR en TENDENCIA (ADX)": dict(estrategia="mr", medida="adx", regimen="tendencia", control=True),
    "19.06 control: tendencia en RANGO (ADX)": dict(estrategia="tend", medida="adx", regimen="rango", control=True),
}
BASE = "19.01 MR solo en RANGO (ADX)"
UMBRALES = {"adx": (20.0, 25.0), "er": (0.2, 0.4)}   # (rango por debajo de, tendencia por encima de)


def vecindad(p: dict) -> dict:
    lo, hi = UMBRALES[p["medida"]]
    f = 0.9, 1.1
    return {f"umbrales x{x}": {**p, "umbrales": (lo * x, hi * x)} for x in f}


def mascara_regimen(ctx, p: dict) -> np.ndarray:
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    lo, hi = p.get("umbrales", UMBRALES[p["medida"]])
    if p["medida"] == "adx":
        a = B.cache(ctx, ("adx", 5), lambda: ind.adx(v.Ha, v.La, v.Ca, 14))[0]
    else:
        def f():
            rth = (v.min_ny >= 570) & (v.min_ny < 960)
            grupo = np.where(rth, v.fecha.astype(np.int64), -1)
            er = ind.eficiencia_sesion(v.C, grupo)
            er[~rth] = np.nan
            return er
        a = B.cache(ctx, "er_sesion5", f)
    return a < lo if p["regimen"] == "rango" else a >= hi


def ordenes_tendencia(ctx, regimen: np.ndarray):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    vw = d["vwap"]
    b = np.arange(len(v))
    ok = B.ventana(v, 600, 900) & B.misma_sesion_rth(v, b, 2) & np.isfinite(vw) & regimen
    h_prev, l_prev = np.r_[np.nan, v.H[:-1]], np.r_[np.nan, v.L[:-1]]
    largo = ok & (v.L <= vw) & (v.C > vw) & (v.C > h_prev)
    corto = ok & (v.H >= vw) & (v.C < vw) & (v.C < l_prev)
    sel = np.flatnonzero(largo | corto)
    dirc = np.where(largo[sel], 1, -1)
    ll = np.minimum.reduce([v.L[np.clip(sel - j, 0, None)] for j in range(3)])
    hh = np.maximum.reduce([v.H[np.clip(sel - j, 0, None)] for j in range(3)])
    return B.df_ordenes(i_sig=v.i1[sel], dir=dirc, stop=np.where(dirc == 1, ll - B.TICK, hh + B.TICK), r_obj=2.0,
                        i_fin=B.fin_por_tiempo(ctx, v, sel))


def ordenes(ctx, p: dict):
    reg = mascara_regimen(ctx, p)
    if p["estrategia"] == "mr":
        return mr.ordenes(ctx, mr.VARIANTES[mr.BASE], regimen=reg)
    return ordenes_tendencia(ctx, reg)


def ejecutar(ctx, p: dict, mult: float = 1.0):
    if p["estrategia"] == "mr":
        return B.correr(ctx, ordenes(ctx, p), mult, max_ses=2, vwap="rth")
    return B.correr(ctx, ordenes(ctx, p), mult)
