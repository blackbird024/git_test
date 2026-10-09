"""Leer la VELA QUE ROMPE el rango de apertura (NQ / MNQ), 2018 - oct 2026.

Rango de apertura: primera vela de 5 min (9:30-9:35) o primeros 15 min (9:30-9:45). La vela de ruptura es la primera vela de
5 min que CIERRA fuera del rango (hasta las 12:00 NY). Su fuerza:
  fuerte   cuerpo ≥ 60 % de su rango y cierra en el tercio a favor
  media    lo demás sin rechazo
  débil    mecha en contra mayor que el cuerpo (cierra fuera pero «rechazada»)
También su tamaño respecto al ATR de la sesión (grande ≥ 5 % · pequeña < 5 %).
Entrada: apertura de la vela siguiente a la de ruptura. Stop: otro lado del rango · mínimo/máximo de la vela de ruptura
· 10 % ATR. Sin objetivo: cierre 16:00. Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_vela_ruptura.py
"""

import itertools

import numpy as np
import pandas as pd

from nq_intraday_research import build_days
from orb15_fvg import exit_px
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    days = build_days("NQ")
    out = {}
    for n, stop in itertools.product((1, 3), ("otro lado", "vela de ruptura", "10% ATR")):
        rows = []
        for x in days:
            B, atr = x["rth"], x["atr"]
            H, L = B[:n, 1].max(), B[:n, 2].min()
            for k in range(n, 29):
                o, h, l, c = B[k]
                s = 1 if c > H else -1 if c < L else 0
                if s == 0:
                    continue
                rng = h - l
                body = abs(c - o)
                with_dir = (c - o) * s > 0
                wick = (min(o, c) - l) if s == 1 else (h - max(o, c))
                loc = ((c - l) / rng if s == 1 else (h - c) / rng) if rng > 0 else 0
                if not with_dir or wick > body:
                    fuerza = "débil (rechazo / color contrario)"
                elif body >= 0.6 * rng and loc >= 2 / 3:
                    fuerza = "fuerte"
                else:
                    fuerza = "media"
                tam = "grande" if rng >= 0.05 * atr else "pequeña"
                e = B[k + 1, 0]
                sl = {"otro lado": L if s == 1 else H, "vela de ruptura": l if s == 1 else h, "10% ATR": e - s * 0.1 * atr}[stop]
                if s * (e - sl) <= 0:
                    break
                u = (s * (exit_px(B, k + 1, s, sl, None) - e) - 1) * 2
                rows.append(dict(y=pd.Timestamp(x["d"]).year, u=u, fuerza=fuerza, tam=tam))
                break
        D = pd.DataFrame(rows)
        rango = "5 min" if n == 1 else "15 min"
        out[(rango, stop, "todas")] = summary(D)
        for f, g in D.groupby("fuerza"):
            out[(rango, stop, f)] = summary(g)
        for f, g in D[D.fuerza == "fuerte"].groupby("tam"):
            out[(rango, stop, f"fuerte y {f}")] = summary(g)
    T = pd.DataFrame(out).T
    T.index.names = ["rango", "stop", "vela de ruptura"]
    T.to_pickle(".lab_cache/orb_vela_ruptura.pkl")
    print(T.to_string())


if __name__ == "__main__":
    main()
