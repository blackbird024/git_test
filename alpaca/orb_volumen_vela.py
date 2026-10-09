"""ORB «la vela habla» + volumen de la vela de la señal (NQ / MNQ, datos de 1 min con volumen), 2018 - oct 2026.

Vela de la señal: 9:30-9:35 (entrada 9:35) o 9:30-9:45 (entrada 9:45).
  vs media 20   volumen de la vela / media de las 20 velas anteriores de esa temporalidad (el «Volume MA» de TradingView)
  RVOL          volumen de la vela / media de la MISMA vela (misma hora) de los 14 días anteriores
Grupos por cociente: < 0,8 · 0,8-1,2 · 1,2-1,6 · ≥ 1,6 (y para «vs media 20»: < 2 · 2-4 · ≥ 4, porque la apertura casi
siempre supera la media). Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_volumen_vela.py
"""

import numpy as np
import pandas as pd

import vwap_globex_8y as V
from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade
from orb_velas_30_60 import summary


def main():
    pd.set_option("display.width", 250)
    m1 = V.load()
    m1.index = m1.index.tz_convert("America/New_York")
    vol = {}
    for tf, rule in (("5m", "5min"), ("15m", "15min")):
        v = m1.volume.resample(rule).sum()
        v = v[v > 0]
        ma20 = v.rolling(20).mean().shift(1)
        hmv = v.index.hour * 60 + v.index.minute
        same = v.groupby(hmv).transform(lambda s: s.rolling(14).mean().shift(1))
        vol[tf] = pd.DataFrame({"v": v, "ma20": ma20, "same": same})
    df = load_5m("NQ")
    t = df.index
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    rows = []
    for x in build_days("NQ"):
        d = pd.Timestamp(x["d"])
        if d not in pre.index:
            continue
        ph, pl = pre.loc[d, ["high", "low"]]
        B, atr = x["rth"], x["atr"]
        c5, c15 = candle(B, 1), candle(B, 3)
        if c5 and ((c5[0] == 1 and B[0, 3] > ph) or (c5[0] == -1 and B[0, 3] < pl)):
            nb, s, k, tf = 1, c5[0], 0.1, "5m"
        elif c15 and not c15[2]:
            nb, s, k, tf = 3, c15[0], 0.15, "15m"
        else:
            continue
        ts = (d + pd.Timedelta(minutes=570)).tz_localize("America/New_York")
        if ts not in vol[tf].index:
            continue
        r = vol[tf].loc[ts]
        rows.append(dict(y=d.year, u=(trade(B, nb, s, k * atr) - 1) * 2, vela=tf,
                         ma20=r.v / r.ma20 if r.ma20 > 0 else np.nan, rvol=r.v / r.same if r.same > 0 else np.nan))
    D = pd.DataFrame(rows).dropna()
    print("todas:", summary(D).to_dict(), "\n")
    D["RVOL"] = pd.cut(D.rvol, [0, 0.8, 1.2, 1.6, 99], labels=["< 0,8", "0,8-1,2", "1,2-1,6", "≥ 1,6"])
    D["vs media 20"] = pd.cut(D.ma20, [0, 2, 4, 999], labels=["< 2×", "2-4×", "≥ 4×"])
    for col in ("RVOL", "vs media 20"):
        print(f"── {col} ──")
        print(D.groupby(col, observed=True).apply(summary, include_groups=False).to_string(), "\n")
    print("── RVOL ≥ 1,2 vs < 1,2 ──")
    print(D.groupby(D.rvol >= 1.2).apply(summary, include_groups=False).to_string())
    print("\nmediana del volumen de la vela de 9:30 frente a su media de 20 velas:", round(D[D.vela == "5m"].ma20.median(), 1), "×")


if __name__ == "__main__":
    main()
