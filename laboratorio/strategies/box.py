""""Teoría de la caja" (versión intradía viral): caja = máximo (PDH) y mínimo (PDL) de la sesión regular de ayer.
Arriba de la caja se vende, abajo se compra, en el medio no se opera. Reglas fijadas antes de ver resultados:

- Solo si la sesión abre DENTRO de la caja. R = PDH − PDL.
- Zona de venta: el 20 % superior de la caja (≥ PDH − 0,2·R). Zona de compra: el 20 % inferior (≤ PDL + 0,2·R).
- Entrada (dos variantes):
    limite        orden límite en el borde interior de la zona (vender en PDH − 0,2·R / comprar en PDL + 0,2·R)
    confirmacion  vela de 5 min que entra en la zona y cierra en contra (bajista arriba / alcista abajo) sin cerrar
                  fuera de la caja → entrada a mercado en la apertura siguiente
- Stop: fuera de la caja, a 0,1·R (PDH + 0,1·R para cortos, PDL − 0,1·R para largos).
- Objetivo (dos variantes): mitad de la caja, o el borde de la zona contraria (PDL + 0,2·R para cortos).
- Entradas de 9:30 a 15:00 ET, cierre forzoso 15:55 ET. Una operación al día (la primera señal).
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK, bars5

ZONE, STOP_OUT, LAST_K, EXIT_K = 0.2, 0.1, 330, 385


def _r(x):
    return round(x / TICK) * TICK


def box(s, ctx, entry="limite", target="media"):
    cd = ctx.get(s.date)
    if not cd or np.isnan(cd.get("prev_high", np.nan)):
        return None
    hi, lo = cd["prev_high"], cd["prev_low"]
    R = hi - lo
    if R <= 0:
        return None
    O, H, L = s.m[:, 0], s.m[:, 1], s.m[:, 2]
    k0 = 0
    while k0 < 5 and np.isnan(O[k0]):
        k0 += 1
    if np.isnan(O[k0]) or not (lo < O[k0] < hi):
        return None
    sell, buy = _r(hi - ZONE * R), _r(lo + ZONE * R)
    stops = {-1: _r(hi + STOP_OUT * R), 1: _r(lo - STOP_OUT * R)}
    tg = {-1: _r((hi + lo) / 2) if target == "media" else buy, 1: _r((hi + lo) / 2) if target == "media" else sell}
    if entry == "limite":
        for k in range(k0, min(LAST_K, s.close_min)):
            if np.isnan(O[k]):
                continue
            up, dn = H[k] >= sell + TICK, L[k] <= buy - TICK
            if up and dn:
                return None
            if up or dn:
                side = -1 if up else 1
                lvl = sell if side == -1 else buy
                return Order(side, "limit", k, stops[side], tg[side], EXIT_K, level=lvl, k_last=k + 1, tag="box_lim")
        return None
    b = bars5(s)
    for i in range(len(b)):
        if 5 * (i + 1) >= LAST_K:
            return None
        o, h, l, c = b[i]
        if np.isnan(c):
            continue
        if h >= sell and c < o and c < hi:
            return Order(-1, "market", 5 * (i + 1), stops[-1], tg[-1], EXIT_K, tag="box_conf")
        if l <= buy and c > o and c > lo:
            return Order(1, "market", 5 * (i + 1), stops[1], tg[1], EXIT_K, tag="box_conf")
    return None
