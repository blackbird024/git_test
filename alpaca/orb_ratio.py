"""ORB «rompe la vela de 9:25» → si no, vela de 15 min sin rechazo: con objetivo fijo (1:1, 1:2, 1:3, 1:5) frente a
sin objetivo (cierre 16:00). NQ / MNQ, 2018 - oct 2026, 1 MNQ, coste 1 punto.

Uso:
    python orb_ratio.py
"""

import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle
from orb15_fvg import exit_px
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    res = {}
    for rr in (1, 2, 3, 5, 0):
        rows = []
        for x in build_days("NQ"):
            d = pd.Timestamp(x["d"])
            if d not in pre.index:
                continue
            ph, pl = pre.loc[d, ["high", "low"]]
            B, atr = x["rth"], x["atr"]
            c5, c15 = candle(B, 1), candle(B, 3)
            if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
                n, s, k = 1, c5[0], 0.1
            elif c15 and not c15[2]:
                n, s, k = 3, c15[0], 0.15
            else:
                continue
            e = B[n, 0]
            risk = k * atr
            tg = e + s * rr * risk if rr else None
            rows.append((d.year, (s * (exit_px(B, n, s, e - s * risk, tg) - e) - 1) * 2))
        R = pd.DataFrame(rows, columns=["y", "u"])
        out = summary(R)
        out["2026 $"] = round(R[R.y == 2026].u.sum())
        res[f"1:{rr}" if rr else "sin objetivo (cierre 22:00)"] = out
    T = pd.DataFrame(res).T
    print(T.to_string())


if __name__ == "__main__":
    main()
