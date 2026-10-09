"""ORB «la vela habla» con GESTIÓN para acertar más (NQ, 2 MNQ), 2018 - oct 2026.

Misma entrada y stop inicial que el ORB. Variantes de gestión con 2 MNQ:
  base             los 2 contratos hasta las 16:00 (= ORB normal × 2)
  parcial X R      se cierra 1 contrato al llegar a +X R (X = 1 · 1,5 · 2); el otro sigue hasta las 16:00
  parcial + BE     igual, y al cerrar el parcial el stop del otro pasa a la entrada (breakeven)
  solo BE          los 2 siguen, pero al llegar a +1 R el stop pasa a la entrada
«Día ganador» = resultado del día > 0. Coste 1 punto por contrato (2 $/punto por MNQ).

Uso:
    python orb_gestion.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle
from orb_velas_30_60 import summary


def manage(B, n, s, risk, partial, be_after_partial, be_only):
    e = B[n, 0]
    sl = e - s * risk
    tp = e + s * partial * risk if partial else None
    be_trig = e + s * risk if be_only else None
    open_ = 2
    pnl = 0.0
    for q in range(n, 78):
        h, l, o = B[q, 1], B[q, 2], B[q, 0]
        if (s == 1 and l <= sl) or (s == -1 and h >= sl):
            px = min(sl, o) if s == 1 else max(sl, o)
            return pnl + open_ * s * (px - e)
        if tp is not None and open_ == 2 and ((s == 1 and h >= tp) or (s == -1 and l <= tp)):
            pnl += s * (tp - e)
            open_ = 1
            if be_after_partial:
                sl = e
        if be_trig is not None and ((s == 1 and h >= be_trig) or (s == -1 and l <= be_trig)):
            sl = e
            be_trig = None
    return pnl + open_ * s * (B[-1, 3] - e)


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    sigs = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, a = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            sigs.append((d.year, B, 1, c5[0], 0.1 * a))
        elif c15 and not c15[2]:
            sigs.append((d.year, B, 3, c15[0], 0.15 * a))
    variants = {"base (2 MNQ hasta 22:00)": (0, False, False), "solo BE a +1R": (0, False, True)}
    for x in (1.0, 1.5, 2.0):
        variants[f"parcial a {x:g}R"] = (x, False, False)
        variants[f"parcial a {x:g}R + BE"] = (x, True, False)
    res = {}
    for name, (p, bep, beo) in variants.items():
        rows = [(y, (manage(B, n, s, r, p, bep, beo) - 2) * 2) for y, B, n, s, r in sigs]
        res[name] = summary(pd.DataFrame(rows, columns=["y", "u"]))
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
