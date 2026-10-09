"""ORB 5 min en NQ / MNQ separado según la FORMA de la primera vela (9:30-9:35 NY), 2018 - oct 2026.

Mismas reglas del ORB 5 min (dirección de la vela, entrada 9:35, stop 10 % del ATR, cierre 16:00). Se agrupan los días por:
  cuerpo     |cierre − apertura| / rango de la vela: < 30 % (indecisa) · 30-60 % · > 60 % (decidida)
  tamaño     rango de la vela / ATR de la sesión: pequeña (< 8 %) · media (8-14 %) · grande (> 14 %)
  cierre     dónde cierra dentro de su rango, a favor de la dirección: en el tercio extremo (fuerte) · medio · contrario (débil)
  mecha contraria  la mecha en contra de la dirección es mayor que el cuerpo (rechazo) o no
Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python orb5_forma_vela.py
"""

import numpy as np
import pandas as pd

from nq_intraday_research import build_days
from orb15_fvg import orb5


def main():
    pd.set_option("display.width", 250)
    rows = []
    for x in build_days("NQ"):
        B = x["rth"]
        o, h, l, c = B[0]
        r = orb5(B, x["atr"])
        if r is None or h - l <= 0:
            continue
        s = 1 if c > o else -1
        body = abs(c - o) / (h - l)
        size = (h - l) / x["atr"]
        loc = (c - l) / (h - l) if s == 1 else (h - c) / (h - l)      # 1 = cierra en el extremo a favor
        wick_against = (min(o, c) - l) if s == 1 else (h - max(o, c))
        rows.append(dict(y=pd.Timestamp(x["d"]).year, u=(r - 1) * 2,
                         cuerpo="< 30 %" if body < 0.3 else "30-60 %" if body < 0.6 else "> 60 %",
                         tamaño="pequeña" if size < 0.08 else "media" if size < 0.14 else "grande",
                         cierre="fuerte (tercio a favor)" if loc > 2 / 3 else "medio" if loc > 1 / 3 else "débil",
                         mecha_contraria="mayor que el cuerpo" if wick_against > abs(c - o) else "menor"))
    D = pd.DataFrame(rows)
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)

    def summary(g):
        d, v = g[g.y < 2023].u, g[g.y >= 2023].u
        eq = g.u.cumsum()
        return pd.Series({"días/año": round(len(g) / 8.75), "acierto": f"{(g.u > 0).mean():.0%}", "$/op": round(g.u.mean(), 1),
                          "dev $/año": round(d.sum() / 5), "pf_dev": pf(d), "val $/año": round(v.sum() / 3.75), "pf_val": pf(v),
                          "peor racha": round((eq.cummax() - eq).max()), "años": f"{(g.groupby('y').u.sum() > 0).sum()}/9"})
    print("TODOS:\n", summary(D).to_string(), "\n")
    for col in ("cuerpo", "tamaño", "cierre", "mecha_contraria"):
        print(f"── por {col} ──")
        print(D.groupby(col).apply(summary, include_groups=False).to_string(), "\n")
    D.to_pickle(".lab_cache/orb5_forma_vela.pkl")


if __name__ == "__main__":
    main()
