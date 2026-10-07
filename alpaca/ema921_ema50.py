"""EMA 9/21 en 5 min con filtro de rango (CHOP) + EMA 50 como filtro de tendencia, en NQ / MNQ.

Sobre la versión de ema921_rango.py (entrada en el retroceso a la EMA 9, salida con el cruce contrario,
máximo 3 al día, 9:30-15:30 NY) se añade la EMA 50 de 5 min de varias formas:
  precio      solo largos si el cierre está por encima de la EMA 50 (cortos por debajo)
  medias      solo largos si la EMA 21 está por encima de la EMA 50 (las tres medias alineadas)
  pendiente   solo largos si la EMA 50 sube respecto a hace 12 velas (1 h)
Coste 1 punto; 1 MNQ; se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python ema921_ema50.py
"""

import numpy as np
import pandas as pd

import ema921_rango as M


def prepare():
    src = open(M.__file__).read()
    code = src.split("def main():")[1].split("    exits =")[0]
    g = dict(vars(M))
    exec("\n".join(line[4:] for line in code.splitlines()), g)
    return g


def main():
    g = prepare()
    o, h, l, c, e9, e21, atr, day, can, last, chop, cs = (g[k] for k in ("o", "h", "l", "c", "e9", "e21", "atr", "day", "can", "last", "chop", "cs"))
    e50 = cs.ewm(span=50, adjust=False).mean().to_numpy()
    dirs = {"sin EMA 50": None, "precio vs EMA 50": np.where(c > e50, 1, -1), "EMA 21 vs EMA 50": np.where(e21 > e50, 1, -1),
            "pendiente EMA 50 (1 h)": np.where(e50 > np.r_[np.full(12, np.nan), e50[:-12]], 1, -1)}
    to_year = lambda x: x.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for th in (38, 40, 42.5, 45, 50, 100):
        for dn, arr in dirs.items():
            fl = 0 if arr is None else 1
            pnl, dd = M.sim(o, h, l, c, e9, e21, atr, chop < th, np.zeros(len(c), np.int64) if arr is None else arr.astype(np.int64),
                            day, can, last, 1, fl, 0.0, 0.0, True, 3, 1.0)
            y = to_year(dd)
            u = pnl * 2
            eq = np.cumsum(u)
            pf = lambda x: round(x[x > 0].sum() / -x[x < 0].sum(), 2)
            d, v = u[y < 2023], u[y >= 2023]
            rows.append({"CHOP <": th if th < 100 else "sin filtro", "EMA 50": dn, "ops/año": round(len(u) / 8.75),
                         "2018-22 $/año": round(d.sum() / 5), "PF dev": pf(d), "2023-26 $/año": round(v.sum() / 3.75), "PF val": pf(v),
                         "peor racha": round((np.maximum.accumulate(eq) - eq).max()), "acierto": round((u > 0).mean(), 2),
                         "años +": f"{(pd.Series(u).groupby(y).sum() > 0).sum()}/9"})
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
