"""ORB «la vela habla» (rompe la vela de 9:25 → si no, 15 min sin rechazo) + filtro de EMA. NQ / MNQ, 2018 - oct 2026.

Filtro: en el momento de la señal (cierre de la vela de 9:30 o de 9:45), el cierre está por encima (compras) / por
debajo (ventas) de la EMA n de la temporalidad tf (última vela cerrada); n = 20 · 50 · 200; tf = 5 min · 15 min · 1 h.
«En contra» = al revés (control). Mismo stop / salida que el ORB. Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_ema_filtro.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    emas = {}
    for tfn, rule, tfm in (("5m", None, 5), ("15m", "15min", 15), ("1h", "60min", 60)):
        b = df if rule is None else df.resample(rule).agg({"close": "last"}).dropna()
        for n in (20, 50, 200):
            e = b.close.ewm(span=n, adjust=False).mean()
            e.index = e.index + pd.Timedelta(minutes=tfm)          # disponible al cerrar la vela
            emas[(tfn, n)] = e
    sig = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, atr = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            n, s, k, px = 1, c5[0], 0.1, B[0, 3]
        elif c15 and not c15[2]:
            n, s, k, px = 3, c15[0], 0.15, B[2, 3]
        else:
            continue
        ts = (d + pd.Timedelta(minutes=570 + 5 * n)).tz_localize("America/New_York")
        u = (trade(B, n, s, k * atr) - 1) * 2
        sig.append((d.year, s, px, ts, u))
    S = pd.DataFrame(sig, columns=["y", "s", "px", "ts", "u"])
    res = {"sin filtro": summary(S)}
    for (tfn, n), e in emas.items():
        val = e.reindex(S.ts, method="ffill").to_numpy()
        side = np.sign(S.px.to_numpy() - val)
        for mode in ("a favor", "en contra"):
            m = side == S.s.to_numpy() if mode == "a favor" else side == -S.s.to_numpy()
            res[f"EMA {n} {tfn} {mode}"] = summary(S[m])
    T = pd.DataFrame(res).T
    T.to_pickle(".lab_cache/orb_ema_filtro.pkl")
    print(T.to_string())


if __name__ == "__main__":
    main()
