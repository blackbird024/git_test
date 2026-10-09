"""A2 · Continuación de tendencia intradía en MNQ. Versión base con pocas reglas, definida antes de probarla.

1. Tendencia superior: cierre de ayer por encima (largos) o por debajo (cortos) de su EMA50 diaria.
2. Confirmación intradía: el cierre de la vela de 5 min de 9:55 (fin de la primera media hora) está a favor de la
   apertura de la sesión (por encima para largos).
3. Retroceso: desde las 10:00, una vela de 5 min que cierra en contra (roja para largos) sin perder la apertura de la
   sesión (mínimo > apertura). Es la vela de retroceso P; si llega otra vela de retroceso, P pasa a ser la nueva.
   Si una vela cierra al otro lado de la apertura de la sesión, la estructura se rompe y no se opera ese día.
4. Confirmación de continuación: orden stop en el máximo de P + 1 tick, válida solo durante la vela siguiente.
5. Stop: mínimo de P − 1 tick (definido antes de entrar). Objetivo 2R. Cierre forzoso 15:50 ET.
   Entradas solo entre las 10:00 y las 12:00 ET. Una operación por día.
Filtros opcionales (se comparan con la base, no se incluyen por defecto):
   ema200  la tendencia superior exige también el cierre de ayer a favor de la EMA200 diaria
   vwap    la vela P cierra a favor del VWAP de la sesión (con volumen de 1 min)
   vol     no operar en el quintil superior de volatilidad diaria (ATR14/precio, percentil de 1 año)
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK, bars5

FIRST_BAR, LAST_ENTRY_K, EXIT_K = 6, 150, 380


def _vwap5(s, nb):
    m = s.m[: 5 * nb]
    tp = (m[:, 1] + m[:, 2] + m[:, 3]) / 3
    v = np.nan_to_num(m[:, 4])
    pv = np.nan_to_num(tp) * v
    cv = np.cumsum(v).reshape(nb, 5)[:, -1]
    cpv = np.cumsum(pv).reshape(nb, 5)[:, -1]
    with np.errstate(invalid="ignore", divide="ignore"):
        return cpv / cv


def trend(s, ctx, ema200=False, vwap=False, vol=False, target_r=2.0):
    cd = ctx.get(s.date)
    if cd is None or np.isnan(cd["ema50"]):
        return None
    side = 1 if cd["prev_close"] > cd["ema50"] else -1
    if ema200 and (np.isnan(cd["ema200"]) or side * (cd["prev_close"] - cd["ema200"]) <= 0):
        return None
    if vol and (np.isnan(cd["vol_rank"]) or cd["vol_rank"] > 0.8):
        return None
    b = bars5(s)
    nb = len(b)
    if nb < FIRST_BAR + 2 or np.isnan(b[0, 0]) or np.isnan(b[5, 3]):
        return None
    sess_open = b[0, 0]
    if side * (b[5, 3] - sess_open) <= 0:
        return None
    vw = _vwap5(s, nb) if vwap else None
    P = None
    for i in range(FIRST_BAR, nb):
        if 5 * i >= LAST_ENTRY_K:
            return None
        o, h, l, c = b[i]
        if np.isnan(c):
            continue
        if P is not None:
            lvl = P[1] + TICK if side == 1 else P[2] - TICK
            hit = (h >= lvl) if side == 1 else (l <= lvl)
            if hit:
                st = P[2] - TICK if side == 1 else P[1] + TICK
                return Order(side, "stop", 5 * i, st, None, EXIT_K, level=lvl, k_last=5 * i + 5,
                             target_r=target_r, tag="trend")
            P = None
        if side * (c - sess_open) <= 0:
            return None                                    # estructura rota
        pull = (c < o and l > sess_open) if side == 1 else (c > o and h < sess_open)
        if pull and (not vwap or side * (c - vw[i]) > 0):
            P = (o, h, l, c)
    return None
