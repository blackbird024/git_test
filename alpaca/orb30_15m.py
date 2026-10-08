"""ORB de 30 min con confirmación: se espera a que una VELA DE 15 MIN CIERRE fuera del rango de los primeros 30 min.

Rango: máximo y mínimo de la primera vela de 30 min (NY 9:30-10:00 NY · Londres 08:00-08:30 Londres).
Señal: la primera vela de 15 min (alineada con la apertura: 10:00-10:15, 10:15-10:30…) que cierra por encima del
rango → compra; por debajo → venta. Entrada al cierre de esa vela. Una operación al día.
Stop: el otro lado del rango · el medio del rango · el extremo contrario de la vela de 15 min de la señal.
Objetivo: 1R (riesgo:beneficio 1:1) — y, para comparar, 2R y sin objetivo (cierre de sesión).
Entradas hasta 2 h después de abrir o hasta 30 min antes del cierre. Salida forzosa: NY 16:00 · Londres 12:00 o 14:25.
Simulación con velas de 5 min (si stop y objetivo caen en la misma vela, cuenta el stop).
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). 2018 - oct 2026.

Uso:
    python orb30_15m.py
"""

import itertools

import numpy as np
import pandas as pd

from orb30_test import days_of


def run(days, o, h, l, c, ses, stop, rr, last_rel, exit_m, cost, usd):
    res = []
    start = 570 if ses == "NY" else 480
    for x in days:
        clock = x["nm"] if ses == "NY" else x["lm"]
        idx = x["idx"]
        rng = idx[(clock >= start) & (clock < start + 30)]
        if len(rng) < 6:
            continue
        H, L = h[rng].max(), l[rng].min()
        mid = (H + L) / 2
        kend_c = idx[clock <= exit_m]
        if len(kend_c) == 0:
            continue
        kend = kend_c[-1]
        last_entry = start + 30 + last_rel if last_rel else exit_m - 30
        t0 = start + 30
        while t0 + 15 <= last_entry + 15 and t0 + 15 <= exit_m:
            bar = idx[(clock >= t0) & (clock < t0 + 15)]
            if len(bar) < 3:
                t0 += 15
                continue
            bc, bh, bl = c[bar[-1]], h[bar].max(), l[bar].min()
            s = 1 if bc > H else -1 if bc < L else 0
            if s == 0:
                t0 += 15
                continue
            e = bc
            sl = {"otro lado": L if s == 1 else H, "medio": mid, "vela 15m": bl if s == 1 else bh}[stop]
            if (s == 1 and e <= sl) or (s == -1 and e >= sl):
                break
            tg = e + s * rr * abs(e - sl) if rr else None
            px = c[kend]
            for q in range(bar[-1] + 1, kend + 1):
                if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                    px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                    break
                if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                    px = tg
                    break
            res.append((x["d"].year, (s * (px - e) - cost) * usd, abs(e - sl) * usd))
            break
    return pd.DataFrame(res, columns=["y", "u", "riesgo"])


def main():
    pd.set_option("display.width", 260)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days, o, h, l, c = days_of(sym)
        for ses, stop, rr, last_rel in itertools.product(("NY", "Londres"), ("otro lado", "medio", "vela 15m"), (1, 2, 0), (120, 0)):
            for ex in ([955] if ses == "NY" else [715, 865]):
                R = run(days, o, h, l, c, ses, stop, rr, last_rel, ex, cost, usd)
                if len(R) < 50:
                    continue
                d, v = R[R.y < 2023].u, R[R.y >= 2023].u
                pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
                eq = R.u.cumsum()
                rows.append(dict(activo=sym, sesion=ses, stop=stop, objetivo=f"{rr}R" if rr else "cierre",
                                 ultima_entrada="2 h" if last_rel else "hasta el final", salida={955: "16:00 NY", 715: "12:00 Lon", 865: "14:25 Lon"}[ex],
                                 ops_año=round(len(R) / 8.75), acierto=round((R.u > 0).mean(), 2), riesgo_med=round(R.riesgo.median()),
                                 dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                                 peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9",
                                 por_año=R.groupby("y").u.sum().round().astype(int).to_dict()))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/orb30_15m.pkl")
    cols = [k for k in R.columns if k != "por_año"]
    print("\n══════ Solo 1:1 ══════")
    print(R[R.objetivo == "1R"][cols].to_string(index=False))
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print("\n% de variantes que ganan en ambos periodos, por objetivo:")
    print(R.groupby(["activo", "sesion", "objetivo"]).apply(both, include_groups=False).unstack().to_string())
    S = R.assign(mn=R[["dev", "val"]].min(axis=1)).sort_values("mn", ascending=False)
    print("\nLas 8 mejores de todo:")
    print(S.head(8)[cols].to_string(index=False))
    for _, x in S.head(2).iterrows():
        print(x.activo, x.sesion, x.stop, x.objetivo, x.por_año)


if __name__ == "__main__":
    main()
