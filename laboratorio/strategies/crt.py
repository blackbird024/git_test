"""CRT (Candle Range Theory) con velas de 4 h en la rejilla de Nueva York (1:00, 5:00, 9:00, 13:00 ET).
Reglas fijadas ANTES de ver resultados:

- C1 (vela de rango) = 5:00-9:00 ET. C2 (vela de manipulación) = 9:00-13:00 ET.
- Bajista: C2 supera el máximo de C1 (barrida) y vuelve dentro → objetivo el mínimo de C1. Alcista: espejo.
Variantes de entrada:
  clasica    se espera al CIERRE de C2 (13:00 ET): si barrió un solo lado de C1 y cerró dentro del rango, entrada a
             mercado a las 13:00 en dirección al otro extremo. Stop: extremo de C2 ± 1 tick.
  cisd       dentro de C2, tras la barrida, un CISD de 5 min: cierre por debajo de la apertura de la primera vela de la
             última serie alcista (que hizo el máximo) y por debajo del máximo de C1. Entrada en la apertura siguiente,
             entre las 9:30 y las 12:30 ET. Stop: máximo desde las 9:00 + 1 tick.
Objetivo: el extremo opuesto de C1 (o 2R como comparación). Cierre forzoso 15:55 ET. Una operación al día.
"""
import numpy as np

from backtests.intraday import Order
from data.loaders import TICK

C1A, C1B, C2A, C2B, OPEN, LAST_CISD = 660, 900, 900, 1140, 930, 1110     # minutos desde las 18:00 ET


def crt(day, ctx, entry="clasica", target="rango"):
    m = day["m24"]
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[C1A:C1B]).all():
        return None
    h1, l1 = np.nanmax(H[C1A:C1B]), np.nanmin(L[C1A:C1B])
    if entry == "clasica":
        if np.isnan(C[C2A:C2B]).all():
            return None
        h2, l2 = np.nanmax(H[C2A:C2B]), np.nanmin(L[C2A:C2B])
        last = C2B - 1
        while np.isnan(C[last]):
            last -= 1
        c2 = C[last]
        up, dn = h2 > h1, l2 < l1
        if up == dn or not (l1 < c2 < h1):
            return None
        side = -1 if up else 1
        stop = h2 + TICK if side == -1 else l2 - TICK
        tgt = l1 if side == -1 else h1
        return _order(side, C2B - OPEN, stop, tgt, target)
    # cisd
    bars = []
    for s in range(C2A, LAST_CISD, 5):
        x = m[s:s + 5]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            y = x[ok]
            bars.append((s + 5, y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3]))
    side = 0
    for j, (e, o, h, l, c) in enumerate(bars):
        if not side:
            if h > h1 and l < l1:
                return None
            side = -1 if h > h1 else (1 if l < l1 else 0)
            if not side:
                continue
        # serie más reciente en contra (alcista para cortos) anterior a esta vela
        q = j - 1
        while q >= 0 and not ((bars[q][4] > bars[q][1]) if side == -1 else (bars[q][4] < bars[q][1])):
            q -= 1
        if q < 0:
            continue
        first = q
        while first - 1 >= 0 and ((bars[first - 1][4] > bars[first - 1][1]) if side == -1 else (bars[first - 1][4] < bars[first - 1][1])):
            first -= 1
        ref = bars[first][1]
        if e < OPEN + 5:
            continue
        if side == -1 and c < ref and c < h1:
            stop = np.nanmax(H[C2A:e]) + TICK
            return _order(-1, e - OPEN, stop, l1, target)
        if side == 1 and c > ref and c > l1:
            stop = np.nanmin(L[C2A:e]) - TICK
            return _order(1, e - OPEN, stop, h1, target)
    return None


def _order(side, k, stop, tgt, target):
    if target == "2R":
        return Order(side, "market", k, stop, None, 385, target_r=2.0, tag="crt")
    return Order(side, "market", k, stop, tgt, 385, tag="crt")
