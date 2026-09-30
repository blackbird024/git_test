"""BOT 24 — RANGO NOCTURNO → NY (NQ, velas de 5 min, salida 15:55).

Hipótesis: la relación entre el rango nocturno (18:00-09:30 NY) y la apertura de NY contiene información sobre
expansión o reversión.

Definiciones (precios ajustados; ONH/ONL = máximo/mínimo de la sesión Globex antes de las 09:30; ONM = punto medio):
  24.1 Ruptura: primera vela de 5 min (09:35-11:30) que cierra por encima de ONH (largo) o por debajo de ONL (corto).
       Stop 1 × ATR(14) de 5 min; objetivo 2R.
  24.2 Reversión (ruptura fallida): entre 09:30 y 11:30 el precio supera ONH (o pierde ONL) y una vela de 5 min
       vuelve a cerrar dentro del rango -> operación hacia ONM (objetivo ONM); stop: extremo RTH hasta esa vela
       ± 1 tick. (Corregido el 30-sep ANTES de ver resultados: la versión "abre fuera del rango" casi nunca ocurre
       porque el rango nocturno incluye el precio de las 09:29; ver CRITERIOS.md, cambios.)
  24.3 Interacción con VWAP: a las 10:00 (cierre de la vela 09:55-10:00), largo si el precio está por encima del VWAP
       y de ONM; corto si está por debajo de ambos. Stop 2 × ATR(14) de 5 min; salida 15:55.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

BOT = "24"
NOMBRE = "Rango nocturno → NY"
HIPOTESIS = ("La relación entre el rango nocturno y la apertura de NY contiene información sobre expansión o "
             "reversión.")
MARCO, SESION, FRECUENCIA = "5m", "NY 09:35-11:30 (salida 15:55)", "intradia"

VARIANTES = {
    "24.1 ruptura del rango nocturno": dict(modelo="ruptura", atr_k=1.0),
    "24.2 reversión al punto medio": dict(modelo="reversion"),
    "24.3 VWAP + punto medio a las 10:00": dict(modelo="vwap", atr_k=2.0),
}
BASE = "24.1 ruptura del rango nocturno"


def vecindad(p: dict) -> dict:
    if "atr_k" in p:
        k = p["atr_k"]
        return {f"atr_k={x:g}": {**p, "atr_k": x} for x in (k * 0.8, k * 1.2)}
    return {"hasta 11:00": {**p, "hasta": 660}, "hasta 12:00": {**p, "hasta": 720}}


def rango_nocturno(ctx) -> pd.DataFrame:
    def f():
        noche = ~ctx.rth & ((ctx.min_ny >= 1080) | (ctx.min_ny < 570))
        idx = np.flatnonzero(noche)
        a = ctx.desfase[idx]
        df = pd.DataFrame({"s": ctx.ses_fecha[idx], "h": ctx.H[idx] - a, "l": ctx.L[idx] - a})
        g = df.groupby("s")
        r = pd.DataFrame({"onh": g.h.max(), "onl": g.l.min(), "n": g.h.size()})
        r = r[r.n >= 300]                                     # noche completa (al menos 5 horas de datos)
        r["onm"] = (r.onh + r.onl) / 2
        r.index = pd.DatetimeIndex(r.index)
        return r
    return B.cache(ctx, "rango_nocturno", f)


def ordenes(ctx, p: dict):
    d = B.velas_ind(ctx, 5)
    v = d["v"]
    r = rango_nocturno(ctx).reindex(pd.DatetimeIndex(v.fecha))   # día NY de la vela RTH = sesión CME
    onh, onl, onm = (r[c].to_numpy() for c in ("onh", "onl", "onm"))
    atr = d["atr14"]
    rth = (v.min_ny >= 570) & (v.min_ny < 960)
    grupo = np.where(rth, v.fecha.astype(np.int64), -1)
    off = ctx.desfase[v.i1]
    hasta = p.get("hasta", 690)
    ok = np.isfinite(onh) & np.isfinite(atr)
    if p["modelo"] == "ruptura":
        ven = ok & B.ventana(v, 575, hasta)
        largo = ven & ind.primero_por_grupo(ven & (v.Ca > onh), grupo)
        corto = ven & ind.primero_por_grupo(ven & (v.Ca < onl), grupo)
        sel = np.flatnonzero(largo | corto)
        return B.df_ordenes(i_sig=v.i1[sel], dir=np.where(largo[sel], 1, -1), stop_dist=p["atr_k"] * atr[sel],
                            r_obj=2.0, i_fin=B.fin_por_tiempo(ctx, v, sel))
    if p["modelo"] == "reversion":
        s_g = pd.Series(grupo)
        hh = pd.Series(np.where(rth, v.H, np.nan)).groupby(s_g).cummax().to_numpy()
        ll = pd.Series(np.where(rth, v.L, np.nan)).groupby(s_g).cummin().to_numpy()
        hh_a, ll_a = hh - off, ll - off
        ven = ok & B.ventana(v, 570, hasta)
        corto = ven & ind.primero_por_grupo(ven & (hh_a > onh) & (v.Ca < onh) & (v.Ca > onm), grupo)
        largo = ven & ind.primero_por_grupo(ven & (ll_a < onl) & (v.Ca > onl) & (v.Ca < onm), grupo)
        sel = np.flatnonzero(largo | corto)
        dirc = np.where(largo[sel], 1, -1)
        return B.df_ordenes(i_sig=v.i1[sel], dir=dirc, stop=np.where(dirc == 1, ll[sel] - B.TICK, hh[sel] + B.TICK),
                            obj=onm[sel] + off[sel], i_fin=B.fin_por_tiempo(ctx, v, sel))
    # vwap: vela que empieza a las 09:55
    vw_a = d["vwap"] - off
    ven = ok & (v.min_ny == 595) & np.isfinite(vw_a)
    largo = ven & (v.Ca > vw_a) & (v.Ca > onm)
    corto = ven & (v.Ca < vw_a) & (v.Ca < onm)
    sel = np.flatnonzero(largo | corto)
    return B.df_ordenes(i_sig=v.i1[sel], dir=np.where(largo[sel], 1, -1), stop_dist=p["atr_k"] * atr[sel],
                        i_fin=B.fin_por_tiempo(ctx, v, sel))


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult, max_ses=1)
