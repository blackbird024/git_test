"""BOT 17 — PULLBACK TREND (NQ, velas de 5 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: en una tendencia establecida, entrar tras un retroceso ofrece mejor relación riesgo/beneficio que
perseguir la ruptura.

Reglas (largos; cortos al revés):
  1. Tendencia: cierre > EMA(200) de 5 min y EMA(200) más alta que 12 velas antes (1 hora).
  2. Retroceso: en alguna de las 3 últimas velas el mínimo tocó la EMA(20) (base) o el VWAP de la sesión.
  3. Disparo: la vela cierra por encima del máximo de la vela anterior -> compra en la apertura siguiente.
  4. Stop: mínimo de las 5 últimas velas − 1 tick. Objetivo 2R (o solo salida 15:55).
"""
from __future__ import annotations

import numpy as np

from bot_lab.strategies import base as B

BOT = "17"
NOMBRE = "Pullback trend"
HIPOTESIS = ("En una tendencia establecida, entrar tras un retroceso ofrece mejor relación riesgo/beneficio que "
             "perseguir la ruptura.")
MARCO, SESION, FRECUENCIA = "5m", "NY 10:00-15:00 (salida 15:55)", "intradia"

_B = dict(ema_larga=200, retroceso="ema20", ema_corta=20, salida="2R")
VARIANTES = {
    "17.01 base EMA200 + EMA20, 2R": _B,
    "17.02 EMA200 + VWAP, 2R": {**_B, "retroceso": "vwap"},
    "17.03 EMA200 + EMA20, salida 15:55": {**_B, "salida": "tiempo"},
    "17.04 EMA200 + VWAP, salida 15:55": {**_B, "retroceso": "vwap", "salida": "tiempo"},
}
BASE = "17.01 base EMA200 + EMA20, 2R"


def vecindad(p: dict) -> dict:
    out = {f"ema_larga={x}": {**p, "ema_larga": x} for x in (180, 220)}
    if p["retroceso"] == "ema20":
        out.update({f"ema_corta={x}": {**p, "ema_corta": x} for x in (15, 25)})
    return out


def ordenes(ctx, p: dict):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    el = B.ema_de(ctx, 5, p["ema_larga"])
    el12 = np.r_[np.full(12, np.nan), el[:-12]]
    arriba = (v.Ca > el) & (el > el12)
    abajo = (v.Ca < el) & (el < el12)
    if p["retroceso"] == "ema20":
        ref_a = B.ema_de(ctx, 5, p["ema_corta"])
        toca_l = v.La <= ref_a
        toca_c = v.Ha >= ref_a
    else:
        vw = d["vwap"]
        toca_l = v.L <= vw
        toca_c = v.H >= vw
    b = np.arange(len(v))
    def alguna(m):
        return m | np.r_[False, m[:-1]] | np.r_[False, False, m[:-2]]
    ok = B.ventana(v, 600, 900) & B.misma_sesion_rth(v, b, 4)
    ha_prev, la_prev = np.r_[np.nan, v.Ha[:-1]], np.r_[np.nan, v.La[:-1]]
    largo = ok & arriba & alguna(toca_l) & (v.Ca > ha_prev)
    corto = ok & abajo & alguna(toca_c) & (v.Ca < la_prev)
    sel = np.flatnonzero(largo | corto)
    dirc = np.where(largo[sel], 1, -1)
    ll = np.minimum.reduce([v.L[np.clip(sel - j, 0, None)] for j in range(5)])
    hh = np.maximum.reduce([v.H[np.clip(sel - j, 0, None)] for j in range(5)])
    cols = dict(i_sig=v.i1[sel], dir=dirc, stop=np.where(dirc == 1, ll - B.TICK, hh + B.TICK),
                i_fin=B.fin_por_tiempo(ctx, v, sel))
    if p["salida"] == "2R":
        cols["r_obj"] = 2.0
    return B.df_ordenes(**cols)


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult)
