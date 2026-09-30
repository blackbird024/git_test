"""BOT 14 — OPENING RANGE BREAKOUT (NQ, 1 min).

Hipótesis: la ruptura del rango inicial de una sesión captura la expansión de volatilidad posterior.

Reglas ORB puro (variante base 14.01):
  1. Rango de apertura (OR) = máximo y mínimo de los primeros N minutos desde las 09:30 NY (N = 15 en la base).
  2. Al cerrar el OR se colocan dos órdenes stop OCO: compra en máximo + 1 tick, venta en mínimo − 1 tick, válidas
     hasta las 12:00 NY. Una operación por sesión.
  3. Stop: el lado opuesto del rango. Salida: 15:55 NY (sin objetivo).
Después se añade UN filtro cada vez sobre la base (VWAP, volumen, compresión del rango, tendencia diaria).
Londres: OR desde las 08:00 de Londres, órdenes válidas 3 h, salida 09:25 NY (antes de la apertura de NY).
Antecedente: archive/reports/estudio_orb_final.md (ORB 5/15/30 con 2R: negativo; con salida por tiempo: t ≤ 1,3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

BOT = "14"
NOMBRE = "Opening range breakout"
HIPOTESIS = "La ruptura del rango inicial de una sesión captura la expansión de volatilidad posterior."
MARCO, SESION, FRECUENCIA = "1m", "NY 09:30-12:00 (salida 15:55) / Londres", "intradia"

_B = dict(sesion="NY", n=15, salida="tiempo", stop="rango", filtro=None)
VARIANTES = {
    "14.01 base OR15 NY puro, salida 15:55": _B,
    "14.02 OR5": {**_B, "n": 5},
    "14.03 OR30": {**_B, "n": 30},
    "14.04 OR15 1R": {**_B, "salida": "1R"},
    "14.05 OR15 1.5R": {**_B, "salida": "1.5R"},
    "14.06 OR15 2R": {**_B, "salida": "2R"},
    "14.07 OR15 trailing 2 ATR15": {**_B, "salida": "trailing"},
    "14.08 OR15 stop 1 ATR15": {**_B, "stop": "atr"},
    "14.09 Londres OR15": {**_B, "sesion": "LDN"},
    "14.10 Londres OR30": {**_B, "sesion": "LDN", "n": 30},
    "14.11 base + filtro VWAP": {**_B, "filtro": "vwap"},
    "14.12 base + filtro volumen": {**_B, "filtro": "volumen"},
    "14.13 base + filtro compresión": {**_B, "filtro": "compresion"},
    "14.14 base + filtro tendencia diaria": {**_B, "filtro": "tendencia"},
}
BASE = "14.01 base OR15 NY puro, salida 15:55"


def vecindad(p: dict) -> dict:
    n = p["n"]
    vec = {5: (3, 7, 10), 15: (10, 20, 25), 30: (20, 25, 40)}[n]
    return {f"OR{x}": {**p, "n": x} for x in vec}


def _rangos(ctx, sesion: str, n: int) -> pd.DataFrame:
    """Una fila por día: índice del último minuto del OR, máximo, mínimo, volumen del OR."""
    def f():
        if sesion == "NY":
            minuto, fecha = ctx.min_ny, ctx.fecha
            ini = 570
        else:
            ldn = ctx.t.tz_convert("Europe/London")
            minuto = (ldn.hour * 60 + ldn.minute).to_numpy()
            fecha = ldn.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
            ini = 480
        m = (minuto >= ini) & (minuto < ini + n)
        idx = np.flatnonzero(m)
        df = pd.DataFrame({"f": fecha[idx], "i": idx, "h": ctx.H[idx], "l": ctx.L[idx], "v": ctx.V[idx],
                           "mi": minuto[idx]})
        g = df.groupby("f")
        r = pd.DataFrame({"i_ult": g.i.max(), "h": g.h.max(), "l": g.l.min(), "vol": g.v.sum(), "velas": g.i.size(),
                          "ult_min": g.mi.max()})
        # OR completo: al menos el 80 % de los minutos y su último minuto dentro del final del OR
        r = r[(r.velas >= 0.8 * n) & (r.ult_min >= ini + n - 3)]
        r["rango"] = r.h - r.l
        r["vol_med"] = r.vol.rolling(20, min_periods=10).median().shift(1)
        r["rango_med"] = r.rango.rolling(20, min_periods=10).median().shift(1)
        return r
    return B.cache(ctx, ("or", sesion, n), f)


def _tendencia_diaria(ctx) -> pd.Series:
    """Por día NY: +1 si el cierre RTH anterior (ajustado) está sobre su EMA50 diaria, −1 si está debajo."""
    def f():
        idx = np.flatnonzero(ctx.rth)
        df = pd.DataFrame({"f": ctx.fecha[idx], "c": ctx.C[idx] - ctx.desfase[idx]})
        c = df.groupby("f").c.last()
        e = pd.Series(ind.ema(c.to_numpy(), 50), index=c.index)
        s = np.sign(c - e).shift(1)
        return s
    return B.cache(ctx, "tend_diaria50", f)


def ordenes(ctx, p: dict):
    r = _rangos(ctx, p["sesion"], p["n"])
    if p["sesion"] == "NY":
        exp_min, fin_min = 720, B.FIN_RTH
        fechas = r.index.to_numpy()
        i_exp = ctx.fin_dia(fechas, exp_min)
        i_fin = ctx.fin_dia(fechas, fin_min)
    else:
        i_sig = r.i_ult.to_numpy()
        i_exp = B.fin_tras_minutos(ctx, i_sig, 180, np.full(len(r), len(ctx.C) - 1))
        fechas_ny = ctx.fecha[i_sig]
        i_fin = ctx.fin_dia(fechas_ny, 565)
        i_exp = np.minimum(i_exp, i_fin)
    i_sig = r.i_ult.to_numpy()
    nl, nc = r.h.to_numpy() + B.TICK, r.l.to_numpy() - B.TICK
    cols = dict(i_sig=i_sig, tipo=1, nivel_l=nl, nivel_c=nc, i_exp=i_exp, i_fin=i_fin)
    d15 = B.velas_ind(ctx, 15)
    # ATR de 15 min conocido al cerrar el OR: el de la última vela de 15 min cerrada
    j = np.searchsorted(d15["v"].i1, i_sig, side="right") - 1
    atr15 = d15["atr14"][np.clip(j, 0, None)]
    if p["stop"] == "rango":
        cols["stop_l"], cols["stop_c"] = nc, nl
    else:
        cols["stop_dist"] = atr15
    if p["salida"].endswith("R"):
        cols["r_obj"] = float(p["salida"][:-1])
    elif p["salida"] == "trailing":
        cols["trail"] = 2 * atr15
    o = B.df_ordenes(**cols)
    f = p["filtro"]
    if f == "vwap":
        vw = ctx.vwap_rth[0][i_sig]
        arriba = ctx.C[i_sig] > vw
        o.loc[~arriba, "nivel_l"] = np.nan
        o.loc[arriba, "nivel_c"] = np.nan
    elif f == "volumen":
        o = o[(r.vol > r.vol_med).to_numpy()]
    elif f == "compresion":
        o = o[(r.rango < r.rango_med).to_numpy()]
    elif f == "tendencia":
        s = _tendencia_diaria(ctx).reindex(r.index).to_numpy()
        o.loc[s != 1, "nivel_l"] = np.nan
        o.loc[s != -1, "nivel_c"] = np.nan
    return o[o.nivel_l.notna() | o.nivel_c.notna()]


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult, max_ses=1)
