"""ORB «la vela habla»: salida cuando el precio CIERRA al otro lado de una EMA (en vez de esperar a las 16:00). NQ, 2018 - oct 2026.

EMA n (9 · 20 · 50) en velas de 5 min o 15 min (calculada con todas las horas). Tras la entrada, si una vela de esa
temporalidad cierra por debajo (compras) / por encima (ventas) de la EMA → se sale en la apertura siguiente.
Se mantiene el stop inicial y el cierre 16:00. Opción: la EMA solo se activa después de estar +1R a favor.
1 MNQ, coste 1 punto (2 $/punto).

Uso:
    python orb_salida_ema.py
"""

import itertools

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
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    o5, h5, l5, c5a = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    pos = pd.Series(np.arange(len(t)), index=t)
    ema_on5 = {}
    for tf, rule, tfm in (("5m", None, 5), ("15m", "15min", 15)):
        b = df if rule is None else df.resample(rule).agg({"close": "last"}).dropna()
        for n in (9, 20, 50):
            e = b.close.ewm(span=n, adjust=False).mean()
            close_t = b.index + pd.Timedelta(minutes=tfm)
            sig = pd.DataFrame({"c": b.close.to_numpy(), "e": e.to_numpy()}, index=close_t)
            ema_on5[(tf, n)] = sig.reindex(t).to_numpy()          # en la vela de 5 min que empieza al cierre de la de tf
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
        if k0 is None or kend is None:
            continue
        sigs.append((d.year, int(k0), int(kend), s, r))
    res = {}
    for key, after1r in [(None, False)] + list(itertools.product(ema_on5.keys(), (False, True))):
        rows = []
        for y, k0, kend, s, r in sigs:
            e = o5[k0]
            sl = e - s * r
            px = c5a[kend]
            armed = not after1r
            for q in range(k0, kend + 1):
                if key is not None and armed and q > k0:          # EMA cruzada al cierre de la vela anterior → salir en la apertura
                    cc, ee = ema_on5[key][q]
                    if np.isfinite(cc) and ((s == 1 and cc < ee) or (s == -1 and cc > ee)):
                        px = o5[q]
                        break
                if (s == 1 and l5[q] <= sl) or (s == -1 and h5[q] >= sl):
                    px = min(sl, o5[q]) if s == 1 else max(sl, o5[q])
                    break
                if not armed and ((s == 1 and h5[q] >= e + r) or (s == -1 and l5[q] <= e - r)):
                    armed = True
            rows.append((y, (s * (px - e) - 1) * 2))
        R = pd.DataFrame(rows, columns=["y", "u"])
        out = summary(R)
        out["2026 $"] = round(R[R.y == 2026].u.sum())
        name = "sin EMA (cierre 22:00)" if key is None else f"cruce EMA {key[1]} {key[0]}" + (" (tras +1R)" if after1r else "")
        res[name] = out
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
