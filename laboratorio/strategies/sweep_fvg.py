"""Barrida del máximo/mínimo de la sesión anterior (15 min) + reversión en un FVG de 1 min ("Robin Hood" del usuario).

Interpretación fijada ANTES de ver resultados (las ambigüedades se prueban como variantes, todas informadas):
1. Niveles ("sesión anterior"):
     pdhl       máximo y mínimo de la sesión regular de ayer (9:30-16:00 ET)
     overnight  máximo y mínimo de la sesión nocturna de hoy (18:00 ET de ayer → 9:29 ET)
2. Barrida: entre las 9:30 y las 11:30 ET el precio supera el nivel (máximo > nivel para cortos, mínimo < nivel
   para largos). Exige que la sesión abra por dentro del nivel. Solo la primera barrida del día; si se barren los
   dos lados en el mismo minuto, no se opera.
     confirm15=False  basta con superar el nivel
     confirm15=True   la vela de 15 min de la barrida debe cerrar de nuevo por dentro del nivel (barrida "fallida")
3. Reversión: después de la barrida (o del cierre de la vela de 15 min si confirm15), primer FVG de 1 min en contra:
     bajista: mínimo de la vela i-2 > máximo de la vela i  (hueco entre ambos)
     alcista: máximo de la vela i-2 < mínimo de la vela i
   Tiene que formarse antes de las 11:30 ET.
4. Entrada: orden límite en el borde del FVG más cercano al precio (para cortos, el máximo de la vela i), válida
   30 minutos. Se cancela si antes toca el stop.
5. Stop: extremo de la barrida (máximo alcanzado desde la barrida hasta el FVG) ± 1 tick.
6. Salidas: "2R_1200" objetivo 2R y cierre 12:00 ET; "2R_cierre" 2R o 15:55; "cierre" sin objetivo hasta 15:55.
Una operación por día.
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK

SWEEP_END_K = 120              # 11:30 ET
EXITS = {"2R_1200": (2.0, 150), "2R_cierre": (2.0, 385), "cierre": (None, 385)}


def sweep_fvg(s, ctx, level="pdhl", confirm15=False, exit="2R_1200"):
    cd = ctx.get(s.date)
    if not cd:
        return None
    hi_lv, lo_lv = (cd.get("prev_high"), cd.get("prev_low")) if level == "pdhl" else (cd.get("on_high"), cd.get("on_low"))
    if hi_lv is None or lo_lv is None or np.isnan(hi_lv) or np.isnan(lo_lv):
        return None
    O, H, L, C = s.m[:, 0], s.m[:, 1], s.m[:, 2], s.m[:, 3]
    k0 = 0
    while k0 < 5 and np.isnan(O[k0]):
        k0 += 1
    op = O[k0]
    if np.isnan(op):
        return None
    side, ks = 0, None
    for k in range(k0, min(SWEEP_END_K, s.close_min)):
        if np.isnan(O[k]):
            continue
        up = op < hi_lv and H[k] > hi_lv
        dn = op > lo_lv and L[k] < lo_lv
        if up and dn:
            return None
        if up or dn:
            side, ks = (-1 if up else 1), k
            break
    if not side:
        return None
    lvl = hi_lv if side == -1 else lo_lv
    start = ks + 1
    if confirm15:
        j = ks // 15
        e = min(15 * j + 15, s.close_min) - 1
        while e > ks and np.isnan(C[e]):
            e -= 1
        if side * (C[e] - lvl) <= 0:            # cortos: cierre de 15 min no ha vuelto por debajo del nivel
            return None
        start = 15 * j + 15
    ext = np.nanmax(H[ks:start]) if side == -1 else np.nanmin(L[ks:start])
    for i in range(max(start, ks + 2), min(SWEEP_END_K, s.close_min)):
        if np.isnan(O[i]):
            continue
        ext = max(ext, H[i]) if side == -1 else min(ext, L[i])
        a = i - 2
        while a >= ks and np.isnan(O[a]):
            a -= 1
        if a < ks:
            continue
        if side == -1 and L[a] > H[i]:
            entry_lvl, stop = H[i], ext + TICK
        elif side == 1 and H[a] < L[i]:
            entry_lvl, stop = L[i], ext - TICK
        else:
            continue
        tr, xk = EXITS[exit]
        return Order(side, "limit", i + 1, stop, None, xk, level=entry_lvl, k_last=i + 31, target_r=tr,
                     tag=f"sweep_{level}")
    return None
