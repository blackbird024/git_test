"""ORB «la vela habla» + LIQUIDEZ (máximos/mínimos de swing sin tomar, idea de Liquidity Swings de LuxAlgo). NQ, 2018 - oct 2026.

Liquidez = pivotes de 1 h (n velas a cada lado, n = 5 y 14 como en LuxAlgo) de los últimos 5 días que el precio todavía NO ha
superado en el momento de la señal. Para cada señal del ORB:
  a favor   distancia al pivote sin tomar más cercano EN la dirección de la operación (máximo para compras), en × ATR de la
            sesión: < 0,25 · 0,25-0,75 · > 0,75 · ninguno (no queda liquidez a favor en 5 días)
  barrida   la vela de apertura (9:30) barrió liquidez EN CONTRA antes de la señal (para compras: su mínimo superó un pivote bajo
            sin tomar) — idea «barre y va»
Coste 1 punto (2 $/punto por MNQ).

Uso:
    python orb_liquidez.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade
from orb_velas_30_60 import summary


def pivots(h1, n):
    hi, lo = h1.high.to_numpy(), h1.low.to_numpy()
    conf = h1.index + pd.Timedelta(hours=n + 1)          # confirmado al cerrar la vela n posiciones después
    P = []
    for j in range(n, len(hi) - n):
        if hi[j] == hi[j - n:j + n + 1].max():
            P.append((conf[j], h1.index[j], hi[j], 1))
        if lo[j] == lo[j - n:j + n + 1].min():
            P.append((conf[j], h1.index[j], lo[j], -1))
    return pd.DataFrame(P, columns=["conf", "t", "lvl", "tipo"]).sort_values("conf").reset_index(drop=True)


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    h1 = df.resample("60min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    pre = df[(t.hour == 9) & (t.minute == 25)]
    pre.index = pre.index.normalize().tz_localize(None)
    hi5, lo5 = df.high, df.low
    for n in (5, 14):
        P = pivots(h1, n)
        rows = []
        for x in build_days("NQ"):
            d = pd.Timestamp(x["d"])
            if d not in pre.index:
                continue
            ph_, pl_ = pre.loc[d, ["high", "low"]]
            B, atr = x["rth"], x["atr"]
            c5, c15 = candle(B, 1), candle(B, 3)
            if c5 and ((c5[0] == 1 and B[0, 3] > ph_) or (c5[0] == -1 and B[0, 3] < pl_)):
                nb, s, k = 1, c5[0], 0.1
            elif c15 and not c15[2]:
                nb, s, k = 3, c15[0], 0.15
            else:
                continue
            open_ts = (d + pd.Timedelta(minutes=570)).tz_localize("America/New_York")
            sig_ts = open_ts + pd.Timedelta(minutes=5 * nb)
            px = B[nb - 1, 3]
            cand = P[(P.conf <= open_ts) & (P.t >= open_ts - pd.Timedelta(days=5))]
            dist, swept = np.nan, False
            for _, p in cand.iterrows():
                seg_h = hi5[p.conf:open_ts - pd.Timedelta(minutes=5)]
                seg_l = lo5[p.conf:open_ts - pd.Timedelta(minutes=5)]
                if p.tipo == 1 and (len(seg_h) and seg_h.max() > p.lvl):
                    continue                                   # ya tomado antes de la apertura
                if p.tipo == -1 and (len(seg_l) and seg_l.min() < p.lvl):
                    continue
                if p.tipo == s:                                # liquidez en la dirección de la operación
                    dd = s * (p.lvl - px) / atr
                    if dd > 0:
                        dist = dd if np.isnan(dist) else min(dist, dd)
                else:                                          # liquidez en contra: ¿la barrió la apertura?
                    lo_open, hi_open = B[:nb, 2].min(), B[:nb, 1].max()
                    if (s == 1 and lo_open < p.lvl) or (s == -1 and hi_open > p.lvl):
                        swept = True
            grp = "ninguna a favor" if np.isnan(dist) else "< 0,25 ATR" if dist < 0.25 else "0,25-0,75 ATR" if dist < 0.75 else "> 0,75 ATR"
            rows.append(dict(y=d.year, u=(trade(B, nb, s, k * atr) - 1) * 2, liquidez_a_favor=grp,
                             barrida_en_contra="sí" if swept else "no"))
        D = pd.DataFrame(rows)
        print(f"\n════ pivotes de 1 h, n = {n} ════")
        print("todas:", summary(D).to_dict())
        print(D.groupby("liquidez_a_favor").apply(summary, include_groups=False).to_string())
        print(D.groupby("barrida_en_contra").apply(summary, include_groups=False).to_string())


if __name__ == "__main__":
    main()
