"""Cruce de EMAs en ORO (GC / MGC): mismas reglas y validación que ema_cross_research.py (NQ).

Diferencias con el Nasdaq:
  · Coste 0,3 puntos por operación ida y vuelta (comisión del micro ~1,5 $ + 1 tic de deslizamiento).
  · Resultados por 1 MGC = 10 $ por punto (1 GC = 100 $ por punto).
  · Ventanas pensadas para el oro: Londres+NY 3:00-13:30 NY (las horas con volumen), COMEX 8:20-13:30 NY
    y Globex (18:00-17:00, cerrado antes de las 17:00).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python gold_ema_research.py
"""

import itertools

import numpy as np
import pandas as pd

import ema_cross_research as E
from crt_backtest import load_5m

COST, USD = 0.3, 10.0
E.USD = USD


def main():
    pd.set_option("display.width", 250)
    df = load_5m("GC")
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    wins = {
        "Londres+NY 3:00-13:30": ((hm >= 180) & (hm < 810), (hm >= 180) & (hm <= 780), hm == 805),
        "COMEX 8:20-13:30": ((hm >= 500) & (hm < 810), (hm >= 500) & (hm <= 780), hm == 805),
        "Globex": ((hm >= 1080) | (hm < 1020), (hm >= 1080) | (hm < 960), hm == 1015),
    }
    tfd = {}
    for tfn, tf in E.TFS.items():
        b = E.tf_frame(df, tf)
        emas = {p: b.close.ewm(span=p, adjust=False).mean() for p in sorted({x for pr in E.PAIRS for x in pr})}
        for f, s in E.PAIRS:
            b[f"s{f}_{s}"] = np.sign(emas[f] - emas[s])
        b["tr"] = np.sign(b.close - b.e200)
        tfd[tfn] = E.align(df, b, ["atr", "tr"] + [f"s{f}_{s}" for f, s in E.PAIRS])
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    to_year = lambda dd: dd.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for tfn, wn, (f, s), lo, fl, sm, fr in itertools.product(E.TFS, wins, E.PAIRS, (0, 1), (0, 1), (0.0, 1.5, 3.0), (1, 0)):
        win, can, last = wins[wn]
        A = tfd[tfn]
        idx = np.flatnonzero(win)
        pnl, dd = E.sim(o[idx], h[idx], l[idx], c[idx], np.nan_to_num(A[f"s{f}_{s}"])[idx], np.nan_to_num(A["tr"])[idx],
                        np.nan_to_num(A["atr"])[idx], gday[idx], can[idx], last[idx], lo, fl, sm, fr, COST)
        if len(pnl) < 50:
            continue
        r = E.evaluate(pnl, dd, to_year)
        rows.append(dict(tf=tfn, ventana=wn, emas=f"{f}/{s}", lado="largos" if lo else "ambos", filtro="EMA200" if fl else "-",
                         stop=f"{sm} ATR" if sm else "-", entrada="cruce" if fr else "estado",
                         dev_ops=round(r["dev"]["ops_y"]), dev_usd=round(r["dev"]["usd_y"]), dev_pf=round(r["dev"]["pf"], 2),
                         val_ops=round(r["val"]["ops_y"]), val_usd=round(r["val"]["usd_y"]), val_pf=round(r["val"]["pf"], 2),
                         val_dd=round(r["val"]["dd"]), val_win=round(r["val"]["win"], 2), años_pos=r["years_pos"], by_year=r["by_year"]))
    r = pd.DataFrame(rows)
    r.to_pickle(".lab_cache/gold_ema.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print("══════ ORO: $/año por 1 MGC · dev 2018-2022 · val 2023-2026 ══════")
    print(r.groupby(["tf", "ventana"]).apply(lambda x: pd.Series({"n": len(x), "% ambos": both(x),
          "med dev": int(x.dev_usd.median()), "med val": int(x.val_usd.median())}), include_groups=False).to_string())
    print(r.groupby(["tf", "emas"]).apply(lambda x: pd.Series({"% ambos": both(x), "med dev": int(x.dev_usd.median()),
          "med val": int(x.val_usd.median())}), include_groups=False).unstack(0).to_string())
    print(r.groupby("lado").apply(lambda x: pd.Series({"% ambos": both(x), "med dev": int(x.dev_usd.median()),
          "med val": int(x.val_usd.median())}), include_groups=False).to_string())
    cols = [k for k in r.columns if k != "by_year"]
    print("\nMejor de cada temporalidad ELEGIDA con 2018-2022:")
    print(r.loc[r.groupby("tf").dev_usd.idxmax(), cols].to_string(index=False))
    print("\nLas 15 con el peor periodo más alto:")
    r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
    print(r.head(15)[cols].to_string(index=False))
    print(r.head(3).by_year.tolist())
    # referencia: comprado siempre en la ventana Londres+NY
    m = wins["Londres+NY 3:00-13:30"][0]
    d = df[m].groupby(gday[m]).agg(o=("open", "first"), c=("close", "last"))
    y = to_year(d.index.to_numpy())
    p = (d.c - d.o - COST) * USD
    print("\nReferencia, largo todos los días 3:00-13:30:", {"dev": round(p[y < 2023].sum() / 5), "val": round(p[y >= 2023].sum() / 3.75)})


if __name__ == "__main__":
    main()
