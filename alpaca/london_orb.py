"""ORB de la primera hora de Londres en NQ / MNQ: robustez alrededor de la única idea de Londres que sobrevivió.

Rango: máximo y mínimo de [inicio, inicio + N min) en hora de Londres. Ruptura con orden STOP en el nivel;
stop en el otro lado (o en el medio); salida a la hora fija (o objetivo k·R); una operación al día.
Filtros probados: a favor del lado del precio frente al cierre de NY de ayer, o frente a la VWAP de Globex;
rango pequeño frente al ATR diario. Misma validación (elige 2018-2022, juzga 2023-2026) y control en ES.

Uso:
    python london_orb.py
"""

import itertools

import numpy as np
import pandas as pd

import london_research as L1
import london_research2 as L2


def exit_at(x, m):
    return int(np.flatnonzero(x["lm"] <= m)[-1])


def orb(days, start=480, n=60, ex=600, stop="lado", rr=None, filt=None, maxr=None):
    out = []
    for x in days:
        s = (x["lm"] >= start) & (x["lm"] < start + n)
        if s.sum() < n // 5:
            continue
        ks = np.flatnonzero(s)
        H, L = x["h"][s].max(), x["l"][s].min()
        if maxr and H - L > maxr * x["atr"]:
            continue
        ke = exit_at(x, ex)
        for k in range(ks[-1] + 1, ke):
            up, dn = x["h"][k] > H, x["l"][k] < L
            if not (up or dn):
                continue
            side = 1 if up else -1
            if filt == "cierre_ny" and np.sign(x["c"][ks[-1]] - x["pC"]) != side:
                break
            if filt == "vwap" and np.sign(x["c"][ks[-1]] - x["vwg"][ks[-1]]) != side:
                break
            e = max(H, x["o"][k]) if up else min(L, x["o"][k])
            sl = (L if up else H) if stop == "lado" else (H + L) / 2
            risk = abs(e - sl)
            out.append((x["d"], L1.trade(x, k, side, e, sl, e + side * rr * risk if rr else None, ke)))
            break
    return out


def main():
    pd.set_option("display.width", 250)
    for sym in ("NQ", "ES"):
        days = L2.build(sym)
        rows = []
        for st, n, ex, sp, rr, fl, mr in itertools.product((420, 450, 480), (30, 60, 90), (600, 630, 660, 720), ("lado", "medio"),
                                                       (None, 2), (None, "cierre_ny", "vwap"), (None, 0.15)):
            if fl == "vwap" and sym != "NQ":
                continue
            if ex <= st + n:
                continue
            r = L1.evaluate(orb(days, st, n, ex, sp, rr, fl, mr))
            if r:
                rows.append(dict(rango=f"{st // 60:02d}:{st % 60:02d}+{n}m", salida=f"{ex // 60}:{ex % 60:02d}", stop=sp,
                                 obj=rr, filtro=fl, max_rango=mr, **r))
        r = pd.DataFrame(rows)
        r.to_pickle(f".lab_cache/london_orb_{sym}.pkl")
        both = lambda g: f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}"
        print(f"\n══════ {sym}: {len(r)} variantes, ganan en ambos periodos: {both(r)} ══════")
        for col in ("rango", "salida", "stop", "filtro", "max_rango"):
            print(r.groupby(col, dropna=False).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g),
                  "med dev": int(g.dev_usd.median()), "med val": int(g.val_usd.median())}), include_groups=False).to_string(), "\n")
        cols = [c for c in r.columns if c != "by_year"]
        print("Mejor ELEGIDA con 2018-2022:")
        print(r.loc[[r.dev_usd.idxmax()], cols].to_string(index=False))
        print("\nLas 12 con el peor periodo más alto:")
        r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(r.head(12)[cols].to_string(index=False))
        print(r.head(3).by_year.tolist())


if __name__ == "__main__":
    main()
