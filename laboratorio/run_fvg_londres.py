"""Estrategia candidata (de run_stats_londres_barrida_max.py, hallazgo A POSTERIORI): ruptura del rango nocturno en
Londres, pullback que entra en el último FVG de 5 min y lo respeta → entrada a favor de la ruptura. NQ/MNQ, hora de Italia.
Reglas fijadas ANTES de ver resultados de esta prueba (los periodos y la regla de selección son los del protocolo):

Rangos: (A) vela de 4 h 0:00-4:00, ventana 4:00-15:30; (B) Asia 0:00-9:00, ventana 9:00-15:30.
1. Ruptura: la primera vela de 5 min (alineada a la hora de Italia) que CIERRA por debajo del mínimo del rango → cortos
   (por encima del máximo → largos). Una operación al día como máximo.
2. FVG bajista (cortos): velas i−1, i, i+1 de 5 min con máximo(i+1) < mínimo(i−1); hueco [máximo(i+1), mínimo(i−1)].
   Se usa el FVG más reciente ya formado, desde la vela de ruptura − 1.
3. Señal: la primera vela posterior que ENTRA en ese FVG (su máximo llega al borde inferior) y cierra por debajo del
   borde superior ("respeta"). Si esa vela ya tocó la mitad del rango, no hay operación. Señales hasta las 15:00 Italia.
4. Entrada a mercado en la apertura siguiente (minuto a minuto con el simulador del laboratorio).
5. Stop (variantes): borde superior del FVG + 1 tick ("fvg"), o la mitad del rango ("mitad").
6. Objetivo (variantes): nivel roto − 0,5 × tamaño del rango ("medio_rango"), 1R o 2R.
7. Cierre forzoso a las 15:25 Italia (antes de la apertura de NY en la mayor parte del año).
Regla de selección (antes de la prueba): esperanza > 0 en desarrollo Y en validación con coste base y n_val >= 30.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from run_crt_italia import N, rome_days
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

RANGES = {"A 0:00-4:00": (0, 240, 240, 930), "B Asia 0:00-9:00": (0, 540, 540, 930)}
LAST_SIG, EXIT_K = 900, 925


def _r(x):
    return round(x / TICK) * TICK


def signal(m, rng, stop_mode, target):
    ra, rb, wa, wb = RANGES[rng]
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[ra:rb]).sum() > (rb - ra) / 2:
        return None
    hi, lo = np.nanmax(H[ra:rb]), np.nanmin(L[ra:rb])
    R = hi - lo
    if R <= 0:
        return None
    mid = (hi + lo) / 2
    ks, b = [], []
    for k in range(wa, wb, 5):
        ok = ~np.isnan(C[k:k + 5])
        if ok.any():
            ks.append(k)
            b.append((np.nanmax(H[k:k + 5]), np.nanmin(L[k:k + 5]), C[k:k + 5][ok][-1]))
    if len(b) < 5:
        return None
    h, l, c = (np.array(x) for x in zip(*b))
    ib = next((i for i in range(len(c)) if c[i] > hi or c[i] < lo), None)
    if ib is None:
        return None
    side = 1 if c[ib] > hi else -1
    edge = hi if side == 1 else lo
    # espacio "corto": para largos se invierte el signo
    xh, xl, xc = (h, l, c) if side == -1 else (-l, -h, -c)
    xmid = mid if side == -1 else -mid
    fvg = None
    for t in range(ib + 1, len(c)):
        if ks[t] + 5 > LAST_SIG:
            return None
        if fvg is not None and xh[t] >= fvg[0]:
            if xc[t] >= fvg[1] or xh[t] >= xmid:
                return None                      # atraviesa el FVG o ya tocó la mitad: no hay operación
            top = fvg[1] if side == -1 else -fvg[1]
            stop = _r(top - side * TICK) if stop_mode == "fvg" else _r(mid)
            k_in = ks[t] + 5
            if target == "medio_rango":
                return Order(side, "market", k_in, stop, _r(edge + side * 0.5 * R), EXIT_K, tag="fvg_ldn")
            return Order(side, "market", k_in, stop, None, EXIT_K, target_r=1.0 if target == "1R" else 2.0,
                         tag="fvg_ldn")
        i = t - 1
        if i - 1 >= ib - 1 and xh[t] < xl[i - 1]:
            fvg = (xh[t], xl[i - 1])
    return None


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"{rg}, stop {sm}, objetivo {tg}": dict(rng=rg, stop_mode=sm, target=tg)
                for rg, sm, tg in itertools.product(RANGES, ("fvg", "mitad"), ("medio_rango", "1R", "2R"))}
    exp = new_experiment("fvg_londres")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                o = signal(m, **p)
                if o is not None:
                    f = simulate(date, m, min(cm, EXIT_K + 1), o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k], minutes_per_session=N)))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            srt = o_.pnl.sort_values(ascending=False)
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             R_medio=o_.R.mean(), R_bruto=(o_.gross_pts * 2 / o_.risk_usd).mean(), ic90_bajo=lo,
                             ic90_alto=hi, riesgo_mediano=o_.risk_usd.median(),
                             top10_pct=100 * srt[:10].sum() / o_.pnl.sum() if o_.pnl.sum() > 0 else np.nan,
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    b = res[res.coste == "base"]
    piv = b.pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    nval = b[b.periodo == "validacion"].set_index("variante").n
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0) & (nval.reindex(piv.index) >= 30)].index.tolist()
    write_manifest(exp, experimento="FVG respetado tras ruptura del rango nocturno en Londres", reglas=__doc__,
                   seleccionadas=sel, periodos={k: [str(a.date()), str(b_.date())] for k, (a, b_) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 70)
    print(b[["variante", "periodo", "n", "pf", "esperanza", "acierto", "R_medio", "R_bruto", "ic90_bajo", "ic90_alto",
             "dd_max", "riesgo_mediano", "top10_pct", "salidas"]].round(2).to_string(index=False))
    print("\nCoste alto, esperanza por periodo:")
    print(res[res.coste == "alto"].pivot_table(index="variante", columns="periodo", values="esperanza",
                                                sort=False).round(2).to_string())
    print("\nSeleccionadas por la regla (dev>0 y val>0):", sel)
    print("→", exp)


if __name__ == "__main__":
    main()
