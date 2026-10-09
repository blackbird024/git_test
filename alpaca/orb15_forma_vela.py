"""ORB con la primera vela de 15 min (9:30-9:45 NY) en NQ / MNQ, separado por su forma, y como segunda opción del ORB 5 min.

Vela de 15 min = máximo/mínimo de las 3 primeras de 5 min, apertura 9:30, cierre 9:45. Entrada en la apertura de las
9:45 en su dirección, stop s × ATR de la sesión (s = 0,1 · 0,15 · 0,2), cierre 16:00.
Forma: cuerpo (< 30 % · 30-60 % · > 60 % del rango) · mecha contraria mayor o menor que el cuerpo.
Combinación «segunda opción»: si la vela de 5 min es válida (mecha contraria < cuerpo) → ORB 5 min a las 9:35;
si no, y la vela de 15 min es válida → ORB 15 min a las 9:45; si ninguna → no se opera.
Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb15_forma_vela.py
"""

import numpy as np
import pandas as pd

from nq_intraday_research import build_days
from orb15_fvg import exit_px


def candle(B, n):
    o, c = B[0, 0], B[n - 1, 3]
    h, l = B[:n, 1].max(), B[:n, 2].min()
    if c == o or h <= l:
        return None
    s = 1 if c > o else -1
    body = abs(c - o)
    wick = (min(o, c) - l) if s == 1 else (h - max(o, c))
    return s, body / (h - l), wick > body


def trade(B, n, s, stop):
    e = B[n, 0]
    return s * (exit_px(B, n, s, e - s * stop, None) - e)


def main():
    pd.set_option("display.width", 250)
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)

    def summary(g):
        d, v = g[g.y < 2023].u, g[g.y >= 2023].u
        eq = g.u.cumsum()
        return pd.Series({"días/año": round(len(g) / 8.75), "acierto": f"{(g.u > 0).mean():.0%}", "$/op": round(g.u.mean(), 1),
                          "dev $/año": round(d.sum() / 5), "pf_dev": pf(d), "val $/año": round(v.sum() / 3.75), "pf_val": pf(v),
                          "peor racha": round((eq.cummax() - eq).max()), "años": f"{(g.groupby('y').u.sum() > 0).sum()}/9"})

    days = build_days("NQ")
    for k in (0.1, 0.15, 0.2):
        rows = []
        for x in days:
            B, atr = x["rth"], x["atr"]
            c15 = candle(B, 3)
            if c15 is None:
                continue
            s, body, rej = c15
            u = (trade(B, 3, s, k * atr) - 1) * 2
            rows.append(dict(y=pd.Timestamp(x["d"]).year, u=u, cuerpo="< 30 %" if body < 0.3 else "30-60 %" if body < 0.6 else "> 60 %",
                             mecha="contraria > cuerpo" if rej else "contraria < cuerpo"))
        D = pd.DataFrame(rows)
        print(f"\n════ Vela de 15 min · stop {k} ATR ════")
        print("todas:", summary(D).to_dict())
        print(D.groupby("cuerpo").apply(summary, include_groups=False).to_string())
        print(D.groupby("mecha").apply(summary, include_groups=False).to_string())
    # combinación: 5 min válida → 5 min; si no, 15 min válida → 15 min
    print("\n════ Combinaciones (stop 5 min = 0,1 ATR; stop 15 min = 0,15 ATR) ════")
    combos = {"solo ORB 5 min (todas)": [], "ORB 5 min filtrado (mecha < cuerpo)": [], "5 min filtrado + 15 min filtrado como 2.ª opción": [],
              "solo ORB 15 min filtrado": []}
    for x in days:
        B, atr, y = x["rth"], x["atr"], pd.Timestamp(x["d"]).year
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5:
            combos["solo ORB 5 min (todas)"].append((y, (trade(B, 1, c5[0], 0.1 * atr) - 1) * 2))
        if c5 and not c5[2]:
            u5 = (trade(B, 1, c5[0], 0.1 * atr) - 1) * 2
            combos["ORB 5 min filtrado (mecha < cuerpo)"].append((y, u5))
            combos["5 min filtrado + 15 min filtrado como 2.ª opción"].append((y, u5))
        elif c15 and not c15[2]:
            combos["5 min filtrado + 15 min filtrado como 2.ª opción"].append((y, (trade(B, 3, c15[0], 0.15 * atr) - 1) * 2))
        if c15 and not c15[2]:
            combos["solo ORB 15 min filtrado"].append((y, (trade(B, 3, c15[0], 0.15 * atr) - 1) * 2))
    print(pd.DataFrame({k: summary(pd.DataFrame(v, columns=["y", "u"])) for k, v in combos.items()}).T.to_string())


if __name__ == "__main__":
    main()
