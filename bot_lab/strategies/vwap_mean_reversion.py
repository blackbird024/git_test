"""BOT 13 — VWAP MEAN REVERSION (NQ, velas de 5 min, RTH).

Hipótesis: cuando NQ se aleja significativamente del VWAP de la sesión, el precio tiende a volver hacia el VWAP.

Reglas (variante base):
  1. Banda = VWAP ± k · desviación (desviación del precio respecto al VWAP ponderada por volumen, desde 09:30 NY).
  2. Entrada "confirmación": la vela de 5 min anterior cerró FUERA de la banda y la actual cierra DENTRO (y todavía
     por encima/debajo del objetivo) -> operación hacia el VWAP en la apertura del minuto siguiente.
  3. Stop: extremo de las 3 últimas velas ± 1 tick. Objetivo: el VWAP (dinámico). Salida 15:55 NY.
  Entradas con velas que empiezan entre 10:00 y 15:00 NY; como máximo 2 operaciones por sesión.
Componentes que se prueban de uno en uno: k (0,5 / 1 / 1,5 / 2), tipo de entrada, objetivo, stop, VWAP de la sesión
Globex y distancia medida en ATR en lugar de desviación.
"""
from __future__ import annotations

import numpy as np

from bot_lab.strategies import base as B

BOT = "13"
NOMBRE = "VWAP mean reversion"
HIPOTESIS = ("Cuando NQ se aleja significativamente del VWAP de la sesión, el precio tiende a volver hacia el VWAP.")
MARCO, SESION, FRECUENCIA = "5m", "NY 10:00-15:00 (salida 15:55)", "intradia"

_B = dict(k=1.5, entrada="confirmacion", objetivo="vwap", stop="extremo", vwap="rth", medida="sd")
VARIANTES = {
    "13.01 base k1.5 confirmación→VWAP stop extremo": _B,
    "13.02 k0.5": {**_B, "k": 0.5},
    "13.03 k1.0": {**_B, "k": 1.0},
    "13.04 k2.0": {**_B, "k": 2.0},
    "13.05 entrada extensión": {**_B, "entrada": "extension"},
    "13.06 entrada rechazo": {**_B, "entrada": "rechazo"},
    "13.07 objetivo 0.5 SD": {**_B, "objetivo": "media_sd"},
    "13.08 objetivo 1.5R": {**_B, "objetivo": "R"},
    "13.09 stop 1 ATR": {**_B, "stop": "atr"},
    "13.10 VWAP Globex": {**_B, "vwap": "globex"},
    "13.11 distancia en ATR": {**_B, "medida": "atr"},
}
BASE = "13.01 base k1.5 confirmación→VWAP stop extremo"


def vecindad(p: dict) -> dict:
    k = p["k"]
    return {f"k={x:g}": {**p, "k": x} for x in (round(k * 0.8, 2), round(k * 0.9, 2), round(k * 1.1, 2), round(k * 1.2, 2))}


def ordenes(ctx, p: dict, regimen: np.ndarray | None = None):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    vw = d["vwap"] if p["vwap"] == "rth" else d["vwap_g"]
    u = (d["sd"] if p["vwap"] == "rth" else d["sd_g"]) if p["medida"] == "sd" else d["atr14"]
    k = p["k"]
    sup, inf = vw + k * u, vw - k * u
    C, H, L = v.C, v.H, v.L
    b = np.arange(len(v))
    ok = B.ventana(v, 600, 900) & B.misma_sesion_rth(v, b, 2) & np.isfinite(u) & (u > 0) & np.isfinite(vw)
    if regimen is not None:
        ok &= regimen
    prev = np.r_[0, b[:-1]]
    if p["entrada"] == "confirmacion":
        corto = (C[prev] > sup[prev]) & (C < sup)
        largo = (C[prev] < inf[prev]) & (C > inf)
    elif p["entrada"] == "extension":
        corto = (C > sup) & (C[prev] <= sup[prev])
        largo = (C < inf) & (C[prev] >= inf[prev])
    else:  # rechazo: mecha fuera de la banda, cierre dentro y en la mitad contraria de la vela
        medio = (H + L) / 2
        corto = (H > sup) & (C < sup) & (C < medio)
        largo = (L < inf) & (C > inf) & (C > medio)
    # objetivo: todavía hay recorrido hasta él
    if p["objetivo"] == "media_sd":
        obj_c, obj_l = vw + 0.5 * u, vw - 0.5 * u
    else:
        obj_c = obj_l = vw
    corto &= ok & (C > obj_c)
    largo &= ok & (C < obj_l)
    sel = np.flatnonzero(corto | largo)
    dirc = np.where(largo[sel], 1, -1)
    i_sig = v.i1[sel]
    cols = dict(i_sig=i_sig, dir=dirc, i_fin=B.fin_por_tiempo(ctx, v, sel))
    if p["stop"] == "extremo":
        hh = np.maximum.reduce([H[np.clip(sel - j, 0, None)] for j in range(3)])
        ll = np.minimum.reduce([L[np.clip(sel - j, 0, None)] for j in range(3)])
        cols["stop"] = np.where(dirc == 1, ll - B.TICK, hh + B.TICK)
    else:
        cols["stop_dist"] = d["atr14"][sel]
    if p["objetivo"] == "vwap":
        cols["obj_vwap"] = True
    elif p["objetivo"] == "media_sd":
        cols["obj"] = np.where(dirc == 1, obj_l[sel], obj_c[sel])
    else:
        cols["r_obj"] = 1.5
    return B.df_ordenes(**cols)


def ejecutar(ctx, p: dict, mult: float = 1.0, regimen=None):
    return B.correr(ctx, ordenes(ctx, p, regimen), mult, max_ses=2, vwap=p["vwap"])
