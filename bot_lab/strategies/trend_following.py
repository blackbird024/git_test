"""BOT 15 — TREND FOLLOWING (NQ, velas de 15 min, entradas 10:00-15:00 NY, salida 15:55).

Hipótesis: cuando NQ presenta una tendencia suficientemente fuerte, las rupturas en su dirección tienen expectativa
positiva (continuación).

Reglas (base, 4 reglas):
  1. Tendencia alcista: cierre > EMA(200) de 15 min y la EMA sube respecto a 4 velas antes (bajista: al revés).
  2. Entrada: cierre por encima del máximo de las 8 velas anteriores (2 horas) a favor de la tendencia.
  3. Stop: 1,5 × ATR(14) de 15 min desde la entrada. Objetivo: 2R.
  4. Salida por tiempo a las 15:55 NY.
Alternativas de tendencia (de una en una): EMA 50, EMA 100, estructura de máximos/mínimos, ADX > 25.
Salida alternativa: trailing de 3 ATR sin objetivo. Las entradas en retroceso se estudian en el BOT 17.
Antecedentes: archive/reports/estudio_ma_mnq.md y estudio_macd_mnq.md (cruces de medias/MACD: negativos o nulos).
"""
from __future__ import annotations

import numpy as np

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

BOT = "15"
NOMBRE = "Trend following"
HIPOTESIS = ("Cuando NQ presenta una tendencia suficientemente fuerte, las rupturas a su favor tienen expectativa "
             "positiva.")
MARCO, SESION, FRECUENCIA = "15m", "NY 10:00-15:00 (salida 15:55)", "intradia"

_B = dict(tendencia="ema", ema=200, ruptura=8, stop_atr=1.5, salida="2R")
VARIANTES = {
    "15.01 base EMA200 ruptura 8 velas, 2R": _B,
    "15.02 EMA50": {**_B, "ema": 50},
    "15.03 EMA100": {**_B, "ema": 100},
    "15.04 tendencia por estructura": {**_B, "tendencia": "estructura"},
    "15.05 tendencia por ADX>25": {**_B, "tendencia": "adx"},
    "15.06 salida trailing 3 ATR": {**_B, "salida": "trailing"},
}
BASE = "15.01 base EMA200 ruptura 8 velas, 2R"


def vecindad(p: dict) -> dict:
    out = {f"ruptura={x}": {**p, "ruptura": x} for x in (6, 10)}
    out.update({f"stop_atr={x}": {**p, "stop_atr": x} for x in (1.25, 1.75)})
    if p["tendencia"] == "ema":
        e = p["ema"]
        out.update({f"ema={x}": {**p, "ema": x} for x in (int(e * 0.9), int(e * 1.1))})
    return out


def direccion_tendencia(ctx, p: dict) -> np.ndarray:
    d = B.velas_ind(ctx, 15)
    v = d["v"]
    if p["tendencia"] == "ema":
        e = B.ema_de(ctx, 15, p["ema"])
        e4 = np.r_[np.full(4, np.nan), e[:-4]]
        return np.where((v.Ca > e) & (e > e4), 1, np.where((v.Ca < e) & (e < e4), -1, 0))
    if p["tendencia"] == "estructura":
        hh = ind.maximo_previo(v.Ha, 8)                   # máximo de b-8..b-1
        hh_ant = np.r_[np.full(8, np.nan), hh[:-8]]       # máximo de b-16..b-9
        ll = ind.minimo_previo(v.La, 8)
        ll_ant = np.r_[np.full(8, np.nan), ll[:-8]]
        return np.where((hh > hh_ant) & (ll > ll_ant), 1, np.where((hh < hh_ant) & (ll < ll_ant), -1, 0))
    a, pdi, mdi = B.cache(ctx, ("adx", 15), lambda: ind.adx(v.Ha, v.La, v.Ca, 14))
    return np.where((a > 25) & (pdi > mdi), 1, np.where((a > 25) & (mdi > pdi), -1, 0))


def ordenes(ctx, p: dict):
    d = B.velas_ind(ctx, 15)
    v = d["v"]
    tend = direccion_tendencia(ctx, p)
    hi, lo = ind.maximo_previo(v.Ha, p["ruptura"]), ind.minimo_previo(v.La, p["ruptura"])
    ok = B.ventana(v, 600, 900) & np.isfinite(d["atr14"])
    largo = ok & (tend == 1) & (v.Ca > hi)
    corto = ok & (tend == -1) & (v.Ca < lo)
    sel = np.flatnonzero(largo | corto)
    cols = dict(i_sig=v.i1[sel], dir=np.where(largo[sel], 1, -1), stop_dist=p["stop_atr"] * d["atr14"][sel],
                i_fin=B.fin_por_tiempo(ctx, v, sel))
    if p["salida"] == "2R":
        cols["r_obj"] = 2.0
    else:
        cols["trail"] = 3 * d["atr14"][sel]
    return B.df_ordenes(**cols)


def ejecutar(ctx, p: dict, mult: float = 1.0):
    return B.correr(ctx, ordenes(ctx, p), mult)
