"""ORB 5 min / 15 min con filtro de forma de vela en la apertura de LONDRES (NQ / MNQ y oro / MGC), 2018 - oct 2026.

Apertura: 08:00 Londres = 09:00 Italia. Primera vela de 5 min (08:00-08:05) y de 15 min (08:00-08:15).
Entrada en la apertura de la vela siguiente en su dirección; stop s × ATR; cierre forzoso 11:00 Londres = 12:00 Italia.
ATR = media de 14 días del rango 08:00-11:00 Londres (la propia ventana). Stops: 5 min 0,1 · 0,15 ATR; 15 min 0,15 · 0,2 ATR.
Forma: «válida» = mecha contraria < cuerpo (como en NY). Cascada 5 → 15 como en NY.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb_london_vela.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from orb15_forma_vela import candle
from orb_velas_30_60 import summary


def trade(B, n, s, stop):
    e = B[n, 0]
    sl = e - s * stop
    for q in range(n, len(B)):
        if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
            return s * ((min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])) - e)
    return s * (B[-1, 3] - e)


def build(sym):
    df = load_5m(sym)
    tl = df.index.tz_convert("Europe/London")
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    arr = df[["open", "high", "low", "close"]].to_numpy()
    out = []
    for d, idx in pd.Series(np.arange(len(df))).groupby(np.array(tl.normalize().asi8)).indices.items():
        idx = np.asarray(idx)
        w = idx[(lm[idx] >= 480) & (lm[idx] < 660)]
        if len(w) != 36:
            continue
        B = arr[w]
        out.append(dict(d=pd.Timestamp(d), B=B, rng=B[:, 1].max() - B[:, 2].min()))
    atr = pd.Series([x["rng"] for x in out]).rolling(14).mean().shift(1).to_numpy()
    for x, a in zip(out, atr):
        x["atr"] = a
    return [x for x in out if np.isfinite(x["atr"])]


def main():
    pd.set_option("display.width", 250)
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days = build(sym)
        res = {}
        for n, k in ((1, 0.1), (1, 0.15), (3, 0.15), (3, 0.2)):
            for filt in ("todas", "sin rechazo", "con rechazo"):
                rows = []
                for x in days:
                    cd = candle(x["B"], n)
                    if cd is None or (filt == "sin rechazo" and cd[2]) or (filt == "con rechazo" and not cd[2]):
                        continue
                    rows.append((x["d"].year, (trade(x["B"], n, cd[0], k * x["atr"]) - cost) * usd))
                res[f"vela {n * 5} min · stop {k} · {filt}"] = summary(pd.DataFrame(rows, columns=["y", "u"]))
        for k5, k15 in ((0.1, 0.15), (0.15, 0.2)):
            rows = []
            for x in days:
                for n, k in ((1, k5), (3, k15)):
                    cd = candle(x["B"], n)
                    if cd and not cd[2]:
                        rows.append((x["d"].year, (trade(x["B"], n, cd[0], k * x["atr"]) - cost) * usd))
                        break
            res[f"cascada 5 → 15 (stops {k5} / {k15})"] = summary(pd.DataFrame(rows, columns=["y", "u"]))
        print(f"\n════ {sym} · Londres 09:00 → 12:00 Italia ════")
        print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
