"""ORB de la primera vela de 5 min con RUPTURA + RETESTEO del nivel (NQ / MNQ), 2018 - oct 2026.

1. Rango: máximo y mínimo de la vela 9:30-9:35 NY (15:30-15:35 Italia).
2. Ruptura: una vela de 5 min CIERRA fuera del rango (entre 9:35 y 12:00 NY). Solo la primera ruptura del día.
3. Retesteo: orden LÍMITE en el nivel roto (máximo del rango para compras, mínimo para ventas), válida hasta
   las 12:00 NY (o solo 30 min tras la ruptura).
4. Stop: otro lado del rango · medio del rango · 10 % del ATR. Objetivo: 1R · 2R · 3R · cierre 16:00.
Referencia: tu ORB 5 min (dirección de la primera vela, entrada 9:35, stop 10 % ATR, cierre 16:00).
Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb5_retesteo.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import build_days
from orb15_fvg import exit_px, orb5, stats


def retest(B, atr, stop, rr, window):
    H, L = B[0, 1], B[0, 2]
    for k in range(1, 30):
        s = 1 if B[k, 3] > H else -1 if B[k, 3] < L else 0
        if s == 0:
            continue
        lvl = H if s == 1 else L
        sl = {"otro lado": L if s == 1 else H, "medio": (H + L) / 2, "10% ATR": lvl - s * 0.1 * atr}[stop]
        if s * (lvl - sl) <= 0:
            return None
        last = 30 if window == "hasta 12:00" else min(30, k + 7)
        for j in range(k + 1, last):
            if (s == 1 and B[j, 2] <= lvl) or (s == -1 and B[j, 1] >= lvl):
                e = min(lvl, B[j, 0]) if s == 1 else max(lvl, B[j, 0])
                if (s == 1 and B[j, 2] <= sl) or (s == -1 and B[j, 1] >= sl):
                    return s * (sl - e)
                risk = s * (e - sl)
                tg = e + s * rr * risk if rr else None
                return s * (exit_px(B, j + 1, s, sl, tg) - e)
        return None
    return None


def main():
    pd.set_option("display.width", 250)
    days = build_days("NQ")
    rows = []
    run = lambda f: [(pd.Timestamp(x["d"]).year, (r - 1.0) * 2.0) for x in days for r in [f(x)] if r is not None]
    stats(rows, "ORB 5 min (tu estrategia)", run(lambda x: orb5(x["rth"], x["atr"])))
    for stop, rr, win in itertools.product(("otro lado", "medio", "10% ATR"), (1.0, 2.0, 3.0, 0.0), ("hasta 12:00", "30 min")):
        stats(rows, f"ruptura + retesteo · SL {stop} · {'cierre' if not rr else f'{rr:g}R'} · {win}",
              run(lambda x: retest(x["rth"], x["atr"], stop, rr, win)))
    T = pd.DataFrame(rows)
    T.to_pickle(".lab_cache/orb5_retesteo.pkl")
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
