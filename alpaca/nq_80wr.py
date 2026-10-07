"""Estrategia de alto acierto en NQ / MNQ: «día de tendencia, sumarse con objetivo corto».

Regla: si antes de la hora límite el precio se ha alejado más de X · ATR diario de la apertura de las 9:30
(día con impulso fuerte), se entra a mercado a favor de ese movimiento en el cierre de la vela de 1 min
que lo confirma; objetivo pequeño (T · ATR), stop amplio (S · ATR); si no toca nada, cierre a las 16:00.
Aquí se comprueba la robustez: umbral X, hora límite, objetivo T y stop S, por periodos y por años.
Costes 1 punto por operación; resultados por 1 MNQ.

Uso:
    python nq_80wr.py
"""

import itertools

import numpy as np
import pandas as pd

import high_winrate_research as H


def main():
    pd.set_option("display.width", 250)
    df, sess, res = H.load("NQ")
    days = H.days_of(df, sess, res)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rows = []
    for th, cut in itertools.product((0.3, 0.35, 0.4, 0.45, 0.5), (630, 660, 720, 780)):
        K, S, P, A, X, Y = [], [], [], [], [], []
        for x in days:
            r, mm = x["r"], x["mm"]
            for j, k in enumerate(r):
                if mm[j] > cut:
                    break
                dv = c[k] - o[r[0]]
                if abs(dv) > th * x["atr"]:
                    K.append(k); S.append(int(np.sign(dv))); P.append(c[k]); A.append(x["atr"]); X.append(r[-1]); Y.append(x["d"].year)
                    break
        K, S, P, A, X, Y = map(np.array, (K, S, P, A, X, Y))
        for tf, sf in itertools.product((0.03, 0.04, 0.05, 0.06, 0.08), (0.3, 0.4, 0.5, 0.6, 0.8)):
            pnl = H.bracket(o, h, l, c, K, S, P.astype(float), tf * A, sf * A, X, 1.0) * 2
            r = dict(umbral=th, hasta=f"{cut // 60}:{cut % 60:02d}", obj=tf, stop=sf)
            for nm_, sel, yrs in (("dev", Y < 2023, 5), ("val", Y >= 2023, 3.75)):
                v = pnl[sel]
                g, ls = v[v > 0].sum(), -v[v < 0].sum()
                eq = np.cumsum(v)
                r |= {f"{nm_}_win": round((v > 0).mean(), 3), f"{nm_}_ops": round(len(v) / yrs), f"{nm_}_usd": round(v.sum() / yrs),
                      f"{nm_}_pf": round(g / ls, 2), f"{nm_}_dd": round((np.maximum.accumulate(eq) - eq).max())}
            by = pd.Series(pnl).groupby(Y).sum()
            r["años"] = f"{(by > 0).sum()}/{len(by)}"
            r["by_year"] = by.round().astype(int).to_dict()
            r["pts_obj_2026"] = round(tf * np.median(A[Y == 2026]))
            r["pts_stop_2026"] = round(sf * np.median(A[Y == 2026]))
            rows.append(r)
    R = pd.DataFrame(rows)
    good = (R.dev_win >= .8) & (R.val_win >= .8) & (R.dev_usd > 0) & (R.val_usd > 0)
    print(f"{len(R)} combinaciones; con ≥80 % de acierto y beneficio en ambos periodos: {good.sum()} ({good.mean():.0%})")
    for col in ("umbral", "hasta", "obj", "stop"):
        print(R.assign(ok=good).groupby(col).agg(ok=("ok", "mean"), win_val=("val_win", "median"), usd_dev=("dev_usd", "median"),
                                                  usd_val=("val_usd", "median")).round(3).to_string(), "\n")
    cols = [k for k in R.columns if k != "by_year"]
    G = R[good].assign(mn=R[good][["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
    print(G.head(15)[cols].to_string(index=False))
    for _, x in G.head(3).iterrows():
        print(x.umbral, x.hasta, x.obj, x.stop, x.by_year)
    R.to_pickle(".lab_cache/nq_80wr.pkl")


if __name__ == "__main__":
    main()
