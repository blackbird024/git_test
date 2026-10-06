"""Silver Bullet de Londres (ICT) con barrida externa: ¿qué pasa cuando Asia ya ha roto el máximo o el mínimo de ayer?

Cada operación del modelo (oro 3-4 NY y Nasdaq 2-5 NY, entrada a mercado tras MSS + FVG, stop en el extremo) se
clasifica según:
  · si Asia (20:00-00:00 NY) ya superó el máximo de ayer o perdió el mínimo de ayer antes de Londres;
  · qué nivel se barrió en Londres: el de ayer o el de Asia;
  · si la operación va a favor o en contra de lo que hizo Asia.

Uso:
    python ict_asia_case.py
"""

import numpy as np
import pandas as pd

import ict_research as I


def trades(sym, w0, w1, xm, cost, usd):
    df = I.bars(sym, 5)
    days = I.day_table(df, 5)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    scan0 = np.array([I.at(x, w0 - 30) for x in days])
    win0 = np.array([I.at(x, w0) for x in days])
    win1 = np.array([I.at(x, w1) for x in days])
    xe = np.array([I.at(x, xm) for x in days])
    lvh, lvl, src_h, src_l = [], [], [], []
    for x, k in zip(days, scan0):
        cand = {"ayer máx": x["pdH"], "ayer mín": x["pdL"], "Asia máx": x["asiaH"], "Asia mín": x["asiaL"]}
        up = {n: v for n, v in cand.items() if v == v and v > c[k]}
        dn = {n: v for n, v in cand.items() if v == v and v < c[k]}
        nh = min(up, key=up.get) if up else None
        nl = max(dn, key=dn.get) if dn else None
        lvh.append(up[nh] if nh else np.nan); src_h.append(nh)
        lvl.append(dn[nl] if nl else np.nan); src_l.append(nl)
    pnl, rm, dd, side = I.engine(o, h, l, c, scan0, win0, win1, xe, np.array(lvh), np.array(lvl), 1, 3, 6, 6, 4, 0, 2, 0.0,
                                 2, 2, cost)
    rows = []
    for p, d, s in zip(pnl, dd, side):
        x = days[d]
        rot_h, rot_l = x["asiaH"] > x["pdH"], x["asiaL"] < x["pdL"]
        asia = "Asia rompió máx de ayer" if rot_h and not rot_l else "Asia rompió mín de ayer" if rot_l and not rot_h \
            else "Asia rompió los dos" if rot_h and rot_l else "Asia dentro del rango de ayer"
        barrido = src_l[d] if s == 1 else src_h[d]
        a_dir = np.sign(c[I.at(x, 0)] - o[x["i0"]])        # dirección de Asia: de las 18:00 a las 00:00 NY
        rows.append(dict(año=x["d"].year, usd=p * usd, lado="largo" if s == 1 else "corto", asia=asia, barrido=barrido,
                         vs_asia="a favor de Asia" if s == a_dir else "contra Asia"))
    return pd.DataFrame(rows)


def show(t, title):
    print(f"\n══════ {title}: {len(t)} operaciones ══════")
    for col in ("asia", "barrido", "vs_asia", "lado"):
        g = t.groupby(col).usd
        print(pd.DataFrame({"ops": g.size(), "gana %": g.apply(lambda v: f"{(v > 0).mean():.0%}"),
                            "$/op": g.mean().round(1), "$ total": g.sum().round(0),
                            "PF": g.apply(lambda v: round(v[v > 0].sum() / -v[v < 0].sum(), 2) if (v < 0).any() else np.inf),
                            "2018-22 $": t[t.año < 2023].groupby(col).usd.sum().round(0),
                            "2023-26 $": t[t.año >= 2023].groupby(col).usd.sum().round(0)}).to_string(), "\n")


def main():
    pd.set_option("display.width", 220)
    show(trades("GC", 180, 240, 690, 0.3, 10.0), "ORO · Silver Bullet Londres 3-4 NY · salida 11:30 NY · $ por 1 MGC")
    show(trades("NQ", 120, 300, 480, 1.0, 2.0), "NASDAQ · killzone Londres 2-5 NY · salida 8:00 NY · $ por 1 MNQ")


if __name__ == "__main__":
    main()
