"""Regla «la vela habla» en la apertura de LONDRES (NQ / MNQ y oro / MGC), 2018 - oct 2026.

Vela previa 07:55-08:00 Londres (08:55-09:00 Italia); primera vela 08:00-08:05 Londres (09:00-09:05 Italia).
Si la primera vela cierra más allá de la previa (verde por encima de su máximo / roja por debajo de su mínimo) → entrada
a las 08:05 en su color; si no, vela de 15 min (08:00-08:15) sin rechazo → entrada 08:15. Stop 10 % / 15 % del ATR de
la ventana 08:00-11:00 Londres; cierre 11:00 Londres (12:00 Italia). Coste NQ 1 punto (2 $/punto) · oro 0,3 (10 $/punto).

Uso:
    python orb_london_previa.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from orb15_forma_vela import candle
from orb_london_vela import trade
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        df = load_5m(sym)
        tl = df.index.tz_convert("Europe/London")
        lm = (tl.hour * 60 + tl.minute).to_numpy()
        arr = df[["open", "high", "low", "close"]].to_numpy()
        days = []
        for d, idx in pd.Series(np.arange(len(df))).groupby(np.array(tl.normalize().asi8)).indices.items():
            idx = np.asarray(idx)
            w = idx[(lm[idx] >= 480) & (lm[idx] < 660)]
            p = idx[lm[idx] == 475]
            if len(w) != 36 or len(p) != 1:
                continue
            days.append(dict(y=pd.Timestamp(d).year, B=arr[w], P=arr[p[0]], rng=arr[w][:, 1].max() - arr[w][:, 2].min()))
        atr = pd.Series([x["rng"] for x in days]).rolling(14).mean().shift(1).to_numpy()
        res = {"todas (ORB normal)": [], "rompe la previa": [], "cierra dentro de la previa": [], "cascada rompe → 15 min": []}
        for x, a in zip(days, atr):
            if not np.isfinite(a):
                continue
            B, P = x["B"], x["P"]
            c5, c15 = candle(B, 1), candle(B, 3)
            if c5 is None:
                continue
            u5 = (trade(B, 1, c5[0], 0.1 * a) - cost) * usd
            brk = (c5[0] == 1 and B[0, 3] > P[1]) or (c5[0] == -1 and B[0, 3] < P[2])
            res["todas (ORB normal)"].append((x["y"], u5))
            res["rompe la previa" if brk else "cierra dentro de la previa"].append((x["y"], u5))
            if brk:
                res["cascada rompe → 15 min"].append((x["y"], u5))
            elif c15 and not c15[2]:
                res["cascada rompe → 15 min"].append((x["y"], (trade(B, 3, c15[0], 0.15 * a) - cost) * usd))
        print(f"\n════ {sym} · Londres 09:00 → 12:00 Italia ════")
        print(pd.DataFrame({k: summary(pd.DataFrame(v, columns=["y", "u"])) for k, v in res.items()}).T.to_string())


if __name__ == "__main__":
    main()
