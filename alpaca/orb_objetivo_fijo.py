"""ORB «la vela habla» con objetivo FIJO en dólares (1 MNQ = 2 $/punto) frente a sin objetivo. NQ, 2018 - oct 2026.

Objetivos: +50 $ (25 pts) · +100 $ (50 pts) · +150 $ (75 pts) · +200 $ (100 pts) · +300 $ (150 pts) · sin objetivo.
Mismo stop (10 % / 15 % del ATR). Coste 1 punto (2 $) por operación.

Uso:
    python orb_objetivo_fijo.py
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
    for usd in (50, 100, 150, 200, 300, 0):
        rows = []
        for y, B, n, s, r in sigs:
            e = B[n, 0]
            tg = e + s * usd / 2 if usd else None
            rows.append((y, (s * (exit_px(B, n, s, e - s * r, tg) - e) - 1) * 2))
        R = pd.DataFrame(rows, columns=["y", "u"])
        out = summary(R)
        out["riesgo medio $"] = round(sum(r for *_, r in sigs) / len(sigs) * 2)
        out["2026 $"] = round(R[R.y == 2026].u.sum())
        res[f"objetivo +{usd} $" if usd else "sin objetivo (22:00)"] = out
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
