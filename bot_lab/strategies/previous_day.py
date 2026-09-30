"""BOT 23 — NIVELES DEL DÍA ANTERIOR (NQ, velas de 5 min, entradas 09:35-15:00 NY, salida 15:55).

Hipótesis: el máximo (PDH), el mínimo (PDL) y el cierre (PDC) de la sesión regular anterior son zonas de liquidez
donde el precio reacciona de forma medible.

Definiciones (todas en precios ajustados por cambio de contrato; niveles del día RTH anterior 09:30-16:00 NY):
  23.1 Ruptura: primera vela del día que CIERRA por encima de PDH (largo) o por debajo de PDL (corto).
       Stop 1 × ATR(14) de 5 min; objetivo 2R.
  23.2 Barrido: primera vela cuyo máximo supera PDH pero cierra por debajo (corto), sin cierre previo del día por
       encima de PDH; simétrico en PDL. Stop: extremo de la vela ± 1 tick; objetivo 2R.
  23.3 Rechazo: la vela se acerca a PDH a menos de 0,25 ATR sin superarlo y cierra bajista (corto), sin toque previo
       del día por encima de PDH; simétrico. Stop: PDH + 0,25 ATR; objetivo 2R.
  23.4 Cierre del hueco: si la apertura RTH deja un hueco respecto a PDC mayor que 0,25 × ATR(14) diario, al cierre de
       la primera vela de 5 min (09:35) se opera hacia PDC si el hueco sigue abierto. Objetivo PDC; stop a la misma
       distancia en contra (1:1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

BOT = "23"
NOMBRE = "Niveles del día anterior"
HIPOTESIS = ("El máximo, el mínimo y el cierre de la sesión regular anterior son zonas de liquidez donde el precio "
             "reacciona de forma medible.")
MARCO, SESION, FRECUENCIA = "5m", "NY 09:35-15:00 (salida 15:55)", "intradia"

VARIANTES = {
    "23.1 ruptura PDH/PDL": dict(modelo="ruptura", atr_k=1.0),
    "23.2 barrido PDH/PDL": dict(modelo="barrido"),
    "23.3 rechazo PDH/PDL": dict(modelo="rechazo", zona=0.25),
    "23.4 cierre del hueco hacia PDC": dict(modelo="hueco", min_hueco=0.25),
}
BASE = "23.1 ruptura PDH/PDL"


def vecindad(p: dict) -> dict:
    if p["modelo"] == "ruptura":
        return {f"atr_k={x}": {**p, "atr_k": x} for x in (0.8, 1.2)}
    if p["modelo"] == "rechazo":
        return {f"zona={x}": {**p, "zona": x} for x in (0.15, 0.35)}
    if p["modelo"] == "hueco":
        return {f"min_hueco={x}": {**p, "min_hueco": x} for x in (0.15, 0.35)}
    return {"objetivo 1.5R": {**p, "r": 1.5}, "objetivo 2.5R": {**p, "r": 2.5}}


def niveles(ctx) -> pd.DataFrame:
    """Por día NY: PDH, PDL, PDC ajustados (del día RTH anterior) y ATR diario de 14 días (RTH, conocido la víspera)."""
    def f():
        idx = np.flatnonzero(ctx.rth)
        a = ctx.desfase[idx]
        df = pd.DataFrame({"f": ctx.fecha[idx], "h": ctx.H[idx] - a, "l": ctx.L[idx] - a, "c": ctx.C[idx] - a,
                           "o": ctx.O[idx] - a})
        g = df.groupby("f")
        d = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
        d["atr_d"] = ind.atr(d.h.to_numpy(), d.l.to_numpy(), d.c.to_numpy(), 14)
        out = pd.DataFrame({"pdh": d.h.shift(1), "pdl": d.l.shift(1), "pdc": d.c.shift(1), "atr_d": d.atr_d.shift(1)},
                           index=d.index)
        return out
    return B.cache(ctx, "niveles_pd", f)


def _por_vela(ctx, v):
    n = niveles(ctx)
    m = n.reindex(pd.DatetimeIndex(v.fecha))
    return (m[c].to_numpy() for c in ("pdh", "pdl", "pdc", "atr_d"))


def _primera_del_dia(mask, v, rth):
    grupo = np.where(rth, v.fecha.astype(np.int64), -1)
    return ind.primero_por_grupo(mask & rth, grupo)


def _ya_hubo(mask, v, rth):
    """True si en una vela ANTERIOR del mismo día RTH ya se cumplió la condición."""
    grupo = pd.Series(np.where(rth, v.fecha.astype(np.int64), -1))
    c = pd.Series((mask & rth).astype(int)).groupby(grupo).cumsum().to_numpy()
    return (c - (mask & rth)) > 0


def ordenes(ctx, p: dict):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    pdh, pdl, pdc, atr_d = _por_vela(ctx, v)
    atr = d["atr14"]
    rth = (v.min_ny >= 570) & (v.min_ny < 960)
    ok = B.ventana(v, 575, 900) & np.isfinite(pdh) & np.isfinite(atr)
    off = ctx.desfase[v.i1]                                   # ajustado -> real
    mod = p["modelo"]
    r = p.get("r", 2.0)
    if mod == "ruptura":
        largo = ok & _primera_del_dia(v.Ca > pdh, v, rth)
        corto = ok & _primera_del_dia(v.Ca < pdl, v, rth)
        sel = np.flatnonzero(largo | corto)
        return B.df_ordenes(i_sig=v.i1[sel], dir=np.where(largo[sel], 1, -1), stop_dist=p["atr_k"] * atr[sel],
                            r_obj=r, i_fin=B.fin_por_tiempo(ctx, v, sel))
    if mod == "barrido":
        cerro_arriba, cerro_abajo = _ya_hubo(v.Ca > pdh, v, rth), _ya_hubo(v.Ca < pdl, v, rth)
        corto = ok & _primera_del_dia((v.Ha > pdh) & (v.Ca < pdh), v, rth) & ~cerro_arriba
        largo = ok & _primera_del_dia((v.La < pdl) & (v.Ca > pdl), v, rth) & ~cerro_abajo
        sel = np.flatnonzero(largo | corto)
        dirc = np.where(largo[sel], 1, -1)
        return B.df_ordenes(i_sig=v.i1[sel], dir=dirc, stop=np.where(dirc == 1, v.L[sel] - B.TICK, v.H[sel] + B.TICK),
                            r_obj=r, i_fin=B.fin_por_tiempo(ctx, v, sel))
    if mod == "rechazo":
        z = p["zona"] * atr
        toco_arriba, toco_abajo = _ya_hubo(v.Ha > pdh, v, rth), _ya_hubo(v.La < pdl, v, rth)
        corto = ok & _primera_del_dia((v.Ha >= pdh - z) & (v.Ha <= pdh) & (v.Ca < v.Oa), v, rth) & ~toco_arriba
        largo = ok & _primera_del_dia((v.La <= pdl + z) & (v.La >= pdl) & (v.Ca > v.Oa), v, rth) & ~toco_abajo
        sel = np.flatnonzero(largo | corto)
        dirc = np.where(largo[sel], 1, -1)
        stop = np.where(dirc == 1, pdl[sel] - z[sel], pdh[sel] + z[sel]) + off[sel]
        return B.df_ordenes(i_sig=v.i1[sel], dir=dirc, stop=stop, r_obj=r, i_fin=B.fin_por_tiempo(ctx, v, sel))
    # hueco: vela de 09:30-09:35
    primera = (v.min_ny == 570) & np.isfinite(pdc) & np.isfinite(atr_d)
    hueco = v.Oa - pdc
    abierto = np.where(hueco > 0, v.Ca > pdc, v.Ca < pdc)
    sel = np.flatnonzero(primera & (np.abs(hueco) > p["min_hueco"] * atr_d) & abierto)
    dirc = np.where(hueco[sel] > 0, -1, 1)
    obj = pdc[sel] + off[sel]
    dist = np.abs(v.C[sel] - obj)
    return B.df_ordenes(i_sig=v.i1[sel], dir=dirc, obj=obj, stop_dist=dist, i_fin=B.fin_por_tiempo(ctx, v, sel))


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult, max_ses=2)
