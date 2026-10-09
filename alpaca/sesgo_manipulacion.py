"""Sesgo del día (RSI 1 h en contra, como el filtro del rango de ayer) + esperar la «manipulación» de un máximo/mínimo.

NQ / MNQ, 2018 - oct 2026. Sesgo a las 9:30 NY: RSI 14 de 1 h > 50 → solo ventas; < 50 → solo compras (el filtro que
funcionó con el rango de ayer). Entrada «ICT»: si el sesgo es de ventas, se espera a que el precio barra un máximo y
vuelva (una vela de 5 min supera el nivel con la mecha y CIERRA por debajo) → venta en la apertura siguiente, stop
1 tick sobre el máximo de la barrida; espejo para compras. Niveles barridos: máximo/mínimo de ayer (9:30-16:00),
máximo/mínimo de los primeros 15 / 30 min. Ventana 9:45-12:00 NY. Objetivo 1R · 2R · cierre 16:00.
Control: lo mismo con el sesgo al revés y sin sesgo. Coste 1 punto (2 $/punto por MNQ).

Uso:
    python sesgo_manipulacion.py
"""

import itertools

import numpy as np
import pandas as pd

import mezcla_filtros as M
from crt_backtest import load_5m


def main():
    pd.set_option("display.width", 250)
    df = load_5m("NQ")
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rsi = M.context(df)["RSI 1h"]
    groups = pd.Series(np.arange(len(df))).groupby(np.array(t.normalize().asi8)).indices
    days = []
    for d in sorted(groups):
        idx = np.asarray(groups[d])
        r = idx[(hm[idx] >= 570) & (hm[idx] < 960)]
        days.append(r if len(r) == 78 else None)
    rows = []
    for lvl_name, mode, rr in itertools.product(("ayer", "15 min", "30 min"), ("sesgo RSI", "sesgo al revés", "sin sesgo"), (1.0, 2.0, 0.0)):
        res = []
        for i in range(1, len(days)):
            r, p = days[i], days[i - 1]
            if r is None or p is None:
                continue
            bias = -int(rsi[r[0]]) if np.isfinite(rsi[r[0]]) else 0
            if mode == "sesgo al revés":
                bias = -bias
            if lvl_name == "ayer":
                H, L, start = h[p].max(), l[p].min(), 3
            else:
                n = 3 if lvl_name == "15 min" else 6
                H, L, start = h[r[:n]].max(), l[r[:n]].min(), n
            for j in range(start, 30):                  # hasta las 12:00
                k = r[j]
                sweep_hi = h[k] > H and c[k] < H
                sweep_lo = l[k] < L and c[k] > L
                s = -1 if sweep_hi else 1 if sweep_lo else 0
                if s == 0 or (mode != "sin sesgo" and s != bias):
                    continue
                e = o[r[j + 1]]
                sl = h[k] + 0.25 if s == -1 else l[k] - 0.25
                risk = s * (e - sl)
                if risk <= 0:
                    break
                tg = e + s * rr * risk if rr else None
                px = c[r[-1]]
                for q in r[j + 1:]:
                    if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                        px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                        break
                    if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                        px = tg
                        break
                res.append((t[k].year, (s * (px - e) - 1) * 2))
                break
        R = pd.DataFrame(res, columns=["y", "u"])
        dv, vv = R[R.y < 2023].u, R[R.y >= 2023].u
        pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
        eq = R.u.cumsum()
        rows.append(dict(nivel_barrido=lvl_name, sesgo=mode, obj=f"{rr:g}R" if rr else "cierre", ops_año=round(len(R) / 8.75),
                         acierto=f"{(R.u > 0).mean():.0%}", dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vv.sum() / 3.75), pf_val=pf(vv),
                         peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))
    T = pd.DataFrame(rows)
    T.to_pickle(".lab_cache/sesgo_manipulacion.pkl")
    print(T.to_string(index=False))


if __name__ == "__main__":
    main()
