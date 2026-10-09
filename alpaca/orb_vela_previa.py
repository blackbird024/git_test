"""ORB 5 min en NQ / MNQ según la relación entre la vela PREVIA (9:25-9:30 NY = 15:25-15:30 Italia) y la primera
vela de NY (9:30-9:35), 2018 - oct 2026.

Grupos (la operación es siempre la del ORB: dirección de la vela de 9:30, entrada 9:35, stop 10 % ATR, cierre 16:00):
  mismo color        la de 9:25 y la de 9:30 son del mismo color
  color contrario    distinto color (sin envolver)
  envolvente         la de 9:30 es de color contrario y su cuerpo envuelve el de la de 9:25
  rompe la previa    la de 9:30 cierra más allá del máximo (verde) / mínimo (roja) de la de 9:25
  dentro de la previa  la de 9:30 cierra dentro del rango de la de 9:25
También se cruza con la regla de la forma (mecha contraria < cuerpo). Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_vela_previa.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_fvg import orb5
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    rows = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        po, ph, pl, pc = pre.loc[d, ["open", "high", "low", "close"]]
        B = x["rth"]
        o, h, l, c = B[0]
        r = orb5(B, x["atr"])
        if r is None or pc == po:
            continue
        s = 1 if c > o else -1
        ps = 1 if pc > po else -1
        wick = (min(o, c) - l) if s == 1 else (h - max(o, c))
        valid = wick < abs(c - o)
        if ps == s:
            rel = "mismo color"
        elif abs(c - o) > abs(pc - po) and min(o, c) <= min(po, pc) and max(o, c) >= max(po, pc):
            rel = "envolvente (contraria)"
        else:
            rel = "color contrario"
        brk = "rompe la previa" if (s == 1 and c > ph) or (s == -1 and c < pl) else "cierra dentro de la previa"
        rows.append(dict(y=d.year, u=(r - 1) * 2, relacion=rel, ruptura=brk, forma="sin rechazo" if valid else "con rechazo"))
    D = pd.DataFrame(rows)
    D.to_pickle(".lab_cache/orb_vela_previa.pkl")
    print("todas:", summary(D).to_dict(), "\n")
    for col in ("relacion", "ruptura"):
        print(D.groupby(col).apply(summary, include_groups=False).to_string(), "\n")
    print("── cruzado con la forma de la vela ──")
    print(D.groupby(["forma", "ruptura"]).apply(summary, include_groups=False).to_string(), "\n")
    print(D.groupby(["forma", "relacion"]).apply(summary, include_groups=False).to_string())


if __name__ == "__main__":
    main()


def cascada():
    """5 min «rompe la previa» → entra 9:35; si no, vela de 15 min sin rechazo → entra 9:45 (stop 0,15 ATR)."""
    from orb15_forma_vela import candle, trade
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    res = {"solo 5 min que rompe la previa": [], "5 min rompe la previa → si no, 15 min sin rechazo": [],
           "5 min sin rechazo → si no, 15 min sin rechazo (la de antes)": []}
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, atr = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        brk = c5 is not None and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl))
        u5 = (trade(B, 1, c5[0], 0.1 * atr) - 1) * 2 if c5 else None
        u15 = (trade(B, 3, c15[0], 0.15 * atr) - 1) * 2 if c15 and not c15[2] else None
        if brk:
            res["solo 5 min que rompe la previa"].append((d.year, u5))
            res["5 min rompe la previa → si no, 15 min sin rechazo"].append((d.year, u5))
        elif u15 is not None:
            res["5 min rompe la previa → si no, 15 min sin rechazo"].append((d.year, u15))
        if c5 and not c5[2]:
            res["5 min sin rechazo → si no, 15 min sin rechazo (la de antes)"].append((d.year, u5))
        elif u15 is not None:
            res["5 min sin rechazo → si no, 15 min sin rechazo (la de antes)"].append((d.year, u15))
    print(pd.DataFrame({k: summary(pd.DataFrame(v, columns=["y", "u"])) for k, v in res.items()}).T.to_string())


if __name__ == "__main__":
    cascada()
