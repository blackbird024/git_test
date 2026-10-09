"""ORB con la primera vela de 30 min y de 1 h (NQ / MNQ), separado por forma, y cascada 5 → 15 → 30 → 60 min.

Igual que orb15_forma_vela.py: vela de n velas de 5 min desde las 9:30 NY; entrada en la apertura siguiente en su
dirección; stop s × ATR de la sesión (s = 0,15 · 0,2 · 0,3); cierre 16:00. «Válida» = mecha contraria < cuerpo.
Cascada: se usa la primera vela válida entre 5 → 15 → 30 → 60 min (stops 0,1 · 0,15 · 0,2 · 0,3 ATR).
Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb_velas_30_60.py
"""

import pandas as pd

from nq_intraday_research import build_days
from orb15_forma_vela import candle, trade


def summary(g):
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    d, v = g[g.y < 2023].u, g[g.y >= 2023].u
    eq = g.u.cumsum()
    return pd.Series({"días/año": round(len(g) / 8.75), "acierto": f"{(g.u > 0).mean():.0%}", "$/op": round(g.u.mean(), 1),
                      "dev $/año": round(d.sum() / 5), "pf_dev": pf(d), "val $/año": round(v.sum() / 3.75), "pf_val": pf(v),
                      "peor racha": round((eq.cummax() - eq).max()), "años": f"{(g.groupby('y').u.sum() > 0).sum()}/9"})


def main():
    pd.set_option("display.width", 250)
    days = build_days("NQ")
    for n, name in ((6, "30 min"), (12, "1 h")):
        for k in (0.15, 0.2, 0.3):
            rows = []
            for x in days:
                cd = candle(x["rth"], n)
                if cd is None:
                    continue
                s, body, rej = cd
                rows.append(dict(y=pd.Timestamp(x["d"]).year, u=(trade(x["rth"], n, s, k * x["atr"]) - 1) * 2,
                                 grupo="sin rechazo" if not rej else "con rechazo"))
            D = pd.DataFrame(rows)
            T = D.groupby("grupo").apply(summary, include_groups=False)
            T.loc["todas"] = summary(D)
            print(f"\n════ Vela de {name} · stop {k} ATR ════")
            print(T.to_string())
    print("\n════ Cascadas ════")
    steps = [(1, 0.1), (3, 0.15), (6, 0.2), (12, 0.3)]
    res = {}
    for upto, label in ((2, "5 → 15"), (3, "5 → 15 → 30"), (4, "5 → 15 → 30 → 60")):
        rows = []
        for x in days:
            for n, k in steps[:upto]:
                cd = candle(x["rth"], n)
                if cd and not cd[2]:
                    rows.append((pd.Timestamp(x["d"]).year, (trade(x["rth"], n, cd[0], k * x["atr"]) - 1) * 2))
                    break
        res[label] = summary(pd.DataFrame(rows, columns=["y", "u"]))
    print(pd.DataFrame(res).T.to_string())


if __name__ == "__main__":
    main()
