"""Foco en el único modelo ICT con resultados consistentes en NQ: killzone de Londres (2:00-5:00 NY) con barrida
de liquidez EXTERNA (máximo/mínimo de ayer o de Asia) → MSS con FVG → entrada. Aquí se prueba a qué hora salir
(fin de Londres, antes de NY, 11:30 NY o cierre 16:00), qué lado funciona y cómo reparte por años.

Uso:
    python ict_london_focus.py
"""

import itertools

import numpy as np
import pandas as pd

import ict_research as I

EXITS = {"5:00 NY (fin killzone)": 300, "8:00 NY": 480, "9:25 NY (antes de NY)": 565, "11:30 NY (cierre Londres)": 690,
         "16:00 NY": None}


def main():
    pd.set_option("display.width", 250)
    for sym, res in (("NQ", 5), ("NQ", 1), ("ES", 5)):
        df = I.bars(sym, res)
        days = I.day_table(df, res)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        years = np.array([x["d"].year for x in days])
        w0, w1 = 120, 300
        scan0 = np.array([I.at(x, w0 - 30) for x in days])
        win0 = np.array([I.at(x, w0) for x in days])
        win1 = np.array([I.at(x, w1) for x in days])
        lvh, lvl = [], []
        for x, k in zip(days, scan0):
            p = c[k]
            lv = np.array([v for v in (x["pdH"], x["pdL"], x["asiaH"], x["asiaL"]) if v == v])
            up, dn = lv[lv > p], lv[lv < p]
            lvh.append(up.min() if len(up) else np.nan)
            lvl.append(dn.max() if len(dn) else np.nan)
        lvh, lvl = np.array(lvh), np.array(lvl)
        b = lambda m: max(1, m // res)
        rows = []
        for (ename, em), sm, (xn, xm) in itertools.product((("mercado", 4), ("fvg", 0), ("ce", 1)), (0, 1), EXITS.items()):
            xe = np.array([x["rth1"] if xm is None else I.at(x, xm) for x in days])
            pnl, rm, dd, side = I.engine(o, h, l, c, scan0, win0, win1, xe, lvh, lvl, 1, b(15), b(30), b(30), em, sm, 2, 0.0,
                                         2, 3 if res == 1 else 2, I.COST)
            if len(pnl) < 20:
                continue
            y = years[dd]
            st = I.stats(pnl, rm, y)
            lg, sh = pnl[side == 1] * I.USD, pnl[side == -1] * I.USD
            rows.append(dict(entrada=ename, stop=["extremo", "vela FVG"][sm], salida=xn, ops=len(pnl),
                             **{k: v for k, v in st.items() if k != "by_year"},
                             largos_usd_año=round(lg.sum() / 8.75), cortos_usd_año=round(sh.sum() / 8.75),
                             R_medio=round(np.nanmean(rm), 2), by_year=st["by_year"]))
        r = pd.DataFrame(rows)
        print(f"\n══════ {sym} {res}m · killzone Londres, barrida externa → MSS + FVG ══════")
        print(r.drop(columns="by_year").to_string(index=False))
        best = r.sort_values("val_usd", ascending=False).iloc[0]
        print("por año (mejor fila):", best.by_year)


if __name__ == "__main__":
    main()
