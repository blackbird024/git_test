"""Patrones de velas clásicos en la APERTURA de NY (NQ / MNQ), 2018 - oct 2026.

Se clasifica la primera vela de 5 min (9:30-9:35 NY) y el par de las dos primeras (9:30-9:40):
  marubozu         cuerpo ≥ 80 % del rango
  vela fuerte      cuerpo 60-80 %
  peonza           cuerpo 30-60 %, mechas parecidas
  doji             cuerpo < 10 %
  martillo         mecha inferior ≥ 2 × cuerpo y mecha superior pequeña (alcista clásico)
  estrella fugaz   mecha superior ≥ 2 × cuerpo y mecha inferior pequeña (bajista clásico)
  envolvente       la 2.ª vela envuelve el cuerpo de la 1.ª y es de color contrario
  vela interior    la 2.ª vela queda dentro del rango de la 1.ª
Para cada patrón se opera: (a) en la dirección del color de la vela (ORB) y (b) en la dirección «clásica» del patrón
(martillo → compra, estrella fugaz → venta, envolvente → su color, interior → ruptura). Entrada en la apertura
siguiente al patrón, stop 10 % ATR (15 % con 2 velas), cierre 16:00. Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_patrones_apertura.py
"""

import numpy as np
import pandas as pd

from nq_intraday_research import build_days
from orb15_fvg import exit_px
from orb_velas_30_60 import summary


def classify(o, h, l, c):
    rng = h - l
    if rng <= 0:
        return None
    body = abs(c - o)
    up, lo = h - max(o, c), min(o, c) - l
    if body / rng < 0.1:
        return "doji"
    if lo >= 2 * body and up <= 0.3 * rng:
        return "martillo"
    if up >= 2 * body and lo <= 0.3 * rng:
        return "estrella fugaz"
    if body / rng >= 0.8:
        return "marubozu"
    if body / rng >= 0.6:
        return "vela fuerte"
    if body / rng >= 0.3:
        return "peonza / normal"
    return "cuerpo pequeño"


def trade(B, k0, s, stop):
    e = B[k0, 0]
    return s * (exit_px(B, k0, s, e - s * stop, None) - e)


def main():
    pd.set_option("display.width", 250)
    rows = []
    for x in build_days("NQ"):
        B, atr, y = x["rth"], x["atr"], pd.Timestamp(x["d"]).year
        o, h, l, c = B[0]
        p = classify(o, h, l, c)
        col = int(np.sign(c - o))
        if p is not None and col != 0:
            classic = 1 if p == "martillo" else -1 if p == "estrella fugaz" else col
            rows.append(dict(y=y, patron=p + (" (verde)" if col == 1 else " (roja)"), modo="color de la vela (ORB)",
                             u=(trade(B, 1, col, 0.1 * atr) - 1) * 2))
            if p in ("martillo", "estrella fugaz"):
                rows.append(dict(y=y, patron=p, modo="dirección clásica", u=(trade(B, 1, classic, 0.1 * atr) - 1) * 2))
        o2, h2, l2, c2 = B[1]
        col2 = int(np.sign(c2 - o2))
        if col != 0 and col2 == -col and abs(c2 - o2) > abs(c - o) and min(o2, c2) <= min(o, c) and max(o2, c2) >= max(o, c):
            rows.append(dict(y=y, patron="envolvente (2 velas)", modo="dirección clásica", u=(trade(B, 2, col2, 0.15 * atr) - 1) * 2))
        if h2 < h and l2 > l:
            for k in range(2, 30):
                if B[k, 1] > h or B[k, 2] < l:
                    if B[k, 1] > h and B[k, 2] < l:
                        break
                    s = 1 if B[k, 1] > h else -1
                    e = max(h, B[k, 0]) if s == 1 else min(l, B[k, 0])
                    rows.append(dict(y=y, patron="vela interior (2 velas)", modo="ruptura de la madre",
                                     u=(s * (exit_px(B, k + 1, s, l if s == 1 else h, None) - e) - 1) * 2))
                    break
    D = pd.DataFrame(rows)
    D.to_pickle(".lab_cache/orb_patrones_apertura.pkl")
    print(D.groupby(["patron", "modo"]).apply(summary, include_groups=False).sort_values("$/op", ascending=False).to_string())


if __name__ == "__main__":
    main()
