"""Sesión de Londres en ORO (GC / MGC): todas las familias probadas en NQ, con costes y valor del punto del oro.

Familias: las de london_research.py (Asia, barridas, ORB de Londres, vela de 5 min, dirección de Asia, franja fija),
london_research2.py (noche, niveles de ayer, ruido, EMAs, RSI2, última hora de NY; sin VWAP porque no hay volumen
antes de 2024), la ORB de la primera hora de london_orb.py y el modelo ICT de la killzone de Londres
(ict_research.py: barrida externa → MSS + FVG). Coste 0,3 puntos; resultados por 1 MGC (10 $/punto).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python gold_london.py
"""

import itertools

import numpy as np
import pandas as pd

import ict_research as I
import london_orb as LO
import london_research as L1
import london_research2 as L2

COST, USD = 0.3, 10.0
for m in (L1, L2, I):
    m.COST, m.USD = COST, USD


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 70)
    rows = []
    d1 = L1.build("GC")
    for fam, grid in L1.GRID.items():
        for p in grid:
            q = {k: v for k, v in p.items() if k != "f"}
            r = L1.evaluate(p["f"](d1, **q))
            if r:
                rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in q.items()), **r))
    print("ronda 1 lista", flush=True)
    d2 = L2.build("GC")
    for fam, grid in L2.GRID.items():
        if fam == "vwap":
            continue
        for p in grid:
            q = {k: v for k, v in p.items() if k != "f"}
            r = L1.evaluate(p["f"](d2, **q))
            if r:
                rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in q.items()), **r))
    print("ronda 2 lista", flush=True)
    for st, n, ex, sp, rr, fl, mr in itertools.product((420, 450, 480), (30, 60, 90), (600, 660, 720, 780), ("lado", "medio"),
                                                   (None, 2), (None, "cierre_ny"), (None, 0.15)):
        if ex <= st + n:
            continue
        r = L1.evaluate(LO.orb(d2, st, n, ex, sp, rr, fl, mr))
        if r:
            rows.append(dict(fam="orb_1a_hora", params=f"{st // 60:02d}:{st % 60:02d}+{n}m salida {ex // 60}:{ex % 60:02d} stop={sp} obj={rr} filtro={fl} max_rango={mr}", **r))
    print("ORB lista", flush=True)
    # modelo ICT killzone de Londres
    df = I.bars("GC", 5)
    days = I.day_table(df, 5)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    years = np.array([x["d"].year for x in days])
    for (w0, w1) in ((120, 300), (180, 240)):
        scan0 = np.array([I.at(x, w0 - 30) for x in days])
        win0 = np.array([I.at(x, w0) for x in days])
        win1 = np.array([I.at(x, w1) for x in days])
        lvh, lvl = [], []
        for x, k in zip(days, scan0):
            lv = np.array([v for v in (x["pdH"], x["pdL"], x["asiaH"], x["asiaL"]) if v == v])
            up, dn = lv[lv > c[k]], lv[lv < c[k]]
            lvh.append(up.min() if len(up) else np.nan)
            lvl.append(dn.max() if len(dn) else np.nan)
        lvh, lvl = np.array(lvh), np.array(lvl)
        for liq, em, sm, (tm, rr), xm in itertools.product((1, 2), (4, 0, 1, 2, 3), (0, 1), ((0, 2.0), (0, 3.0), (1, 0.0), (2, 0.0)),
                                                           (480, 690, None)):
            xe = np.array([x["rth1"] if xm is None else I.at(x, xm) for x in days])
            pnl, rm, dd, side = I.engine(o, h, l, c, scan0, win0, win1, xe, lvh, lvl, liq, 3, 6, 6, em, sm, tm, rr, 2, 2, COST)
            if len(pnl) < 40:
                continue
            y = years[dd]
            r = L1.evaluate(list(zip(pd.to_datetime([f"{v}-06-30" for v in y]), pnl)))
            if r:
                rows.append(dict(fam="ict_killzone", params=f"ventana {w0 // 60}-{w1 // 60} NY liq={'externa' if liq == 1 else 'interna'} "
                                 f"entrada={['fvg', 'ce', 'ote', 'unicorn', 'mercado'][em]} stop={['extremo', 'vela FVG'][sm]} "
                                 f"obj={ {0: f'{rr:g}R', 1: 'liquidez', 2: 'hora'}[tm]} salida={xm or 960}", **r))
    print("ICT lista", flush=True)
    r = pd.DataFrame(rows)
    r.to_pickle(".lab_cache/gold_london.pkl")
    both = lambda g: f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}"
    print(f"\n══════════ ORO, sesión de Londres: {len(r)} variantes · $/año por 1 MGC · dev 2018-2022 · val 2023-2026 ══════════")
    print(r.groupby("fam").apply(lambda g: pd.Series({"variantes": len(g), "% gana ambos": both(g),
          "mediana dev": int(g.dev_usd.median()), "mediana val": int(g.val_usd.median())}), include_groups=False).to_string())
    cols = [k for k in r.columns if k != "by_year"]
    print("\nMejor de cada familia ELEGIDA con 2018-2022:")
    print(r.loc[r.groupby("fam").dev_usd.idxmax(), cols].to_string(index=False))
    print("\nLas 20 con el peor periodo más alto:")
    r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
    print(r.head(20)[cols].to_string(index=False))
    for _, x in r.head(5).iterrows():
        print(x.fam, x.params, x.by_year)


if __name__ == "__main__":
    main()
