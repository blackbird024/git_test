"""ORB «la vela habla»: salida cuando la EMA 20 cruza la EMA 50 en contra (5 min o 15 min), frente a precio vs EMA 50 y 22:00.
NQ, 2018 - oct 2026, 1 MNQ, coste 1 punto (2 $/punto). Se mantiene el stop inicial y el cierre 16:00 NY.

Uso:
    python orb_salida_cruce_emas.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    o5, h5, l5, c5a = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    pos = pd.Series(np.arange(len(t)), index=t)
    sig = {}
    for tf, rule, tfm in (("5m", None, 5), ("15m", "15min", 15)):
        b = df if rule is None else df.resample(rule).agg({"close": "last"}).dropna()
        e20, e50 = b.close.ewm(span=20, adjust=False).mean(), b.close.ewm(span=50, adjust=False).mean()
        idx = b.index + pd.Timedelta(minutes=tfm)
        sig[("cruce EMA 20/50", tf)] = pd.Series(np.sign(e20 - e50).to_numpy(), index=idx).reindex(t).to_numpy()
        sig[("precio vs EMA 50", tf)] = pd.Series(np.sign(b.close - e50).to_numpy(), index=idx).reindex(t).to_numpy()
    sigs = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, a = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            n, s, r = 1, c5[0], 0.1 * a
        elif c15 and not c15[2]:
            n, s, r = 3, c15[0], 0.15 * a
        else:
            continue
        k0 = pos.get((d + pd.Timedelta(minutes=570 + 5 * n)).tz_localize("America/New_York"))
        kend = pos.get((d + pd.Timedelta(minutes=955)).tz_localize("America/New_York"))
        if k0 is not None and kend is not None:
            sigs.append((d.year, int(k0), int(kend), s, r))
    res = {}
    for key in [None] + list(sig.keys()):
        rows, already = [], 0
        for y, k0, kend, s, r in sigs:
            e = o5[k0]
            sl = e - s * r
            px = c5a[kend]
            if key is not None and np.isfinite(sig[key][k0]) and sig[key][k0] == -s:
                already += 1
            for q in range(k0, kend + 1):
                if key is not None and q > k0 and np.isfinite(sig[key][q]) and sig[key][q] == -s and sig[key][q - 1] != -s:
                    px = o5[q]
                    break
                if (s == 1 and l5[q] <= sl) or (s == -1 and h5[q] >= sl):
                    px = min(sl, o5[q]) if s == 1 else max(sl, o5[q])
                    break
            rows.append((y, (s * (px - e) - 1) * 2))
        R = pd.DataFrame(rows, columns=["y", "u"])
        out = summary(R)
        out["2026 $"] = round(R[R.y == 2026].u.sum())
        out["% días ya en contra al entrar"] = f"{already / len(sigs):.0%}" if key else "—"
        res["sin salida por EMA (22:00)" if key is None else f"{key[0]} {key[1]}"] = out
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
