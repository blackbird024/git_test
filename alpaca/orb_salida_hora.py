"""ORB «la vela habla» con salida a distintas horas (fin de la killzone de NY 11:00, 12:00, 13:30, 16:00). NQ, 2018 - oct 2026.

1 MNQ, mismo stop. Hora NY (Italia = NY + 6 h casi todo el año). Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_salida_hora.py
"""

import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle
from orb_velas_30_60 import summary


def run(B, n, s, risk, last):
    e = B[n, 0]
    sl = e - s * risk
    for q in range(n, last + 1):
        if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
            return s * ((min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])) - e)
    return s * (B[last, 3] - e)


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
    res = {}
    for label, last in (("11:00 NY = 17:00 Italia (fin killzone)", 17), ("12:00 NY = 18:00 Italia", 29), ("13:30 NY = 19:30 Italia", 47),
                        ("15:00 NY = 21:00 Italia", 65), ("16:00 NY = 22:00 Italia (actual)", 77)):
        rows = [(y, (run(B, n, s, r, last) - 1) * 2) for y, B, n, s, r in sigs]
        R = pd.DataFrame(rows, columns=["y", "u"])
        out = summary(R)
        out["2026 $"] = round(R[R.y == 2026].u.sum())
        res[label] = out
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
