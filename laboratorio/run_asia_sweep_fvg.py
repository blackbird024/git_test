"""Estrategia del usuario (ICT, killzone de Londres), NQ/MNQ, hora de Italia. Reglas fijadas ANTES de ver resultados:

1. Rango asiático: máximo y mínimo de 2:00 a 6:00 Italia (velas de 1 min).
2. Barrida: desde las 6:00, la primera vela (del marco elegido) cuyo máximo supera el máximo de Asia → se buscan CORTOS
   (o cuyo mínimo perfora el mínimo de Asia → LARGOS). Se usa el primer lado barrido del día.
3. FVG en la dirección del giro (cortos: FVG bajista, máximo de la vela i+1 < mínimo de la vela i−1), formado DESPUÉS
   de la barrida (la vela i−1 es la de la barrida o posterior). Se usa el más reciente ya formado.
4. Pullback que entra en el FVG (su máximo llega al borde inferior del hueco) y lo RESPETA (cierra por debajo del borde
   superior) → entrada a mercado en la apertura siguiente.
   Se anula si antes de la entrada el precio supera el extremo de la barrida, o ya ha tocado el objetivo.
5. Killzone: barrida, FVG y señal antes de las 11:00 Italia (la entrada, como muy tarde, en la vela de las 11:00).
6. Marco del FVG (variantes): 5 min o 15 min (velas alineadas a la hora de Italia).
7. Stop (variantes): extremo de la barrida + 1 tick, o borde superior del FVG + 1 tick.
8. Objetivo (variantes): el lado opuesto del rango asiático, o 2R. Cierre forzoso a las 15:25 Italia.
Variante "continuación" (segunda lectura de la frase del usuario): tras barrer el máximo de Asia, el pullback BAJA a un
FVG ALCISTA de la subida (tercera vela del FVG en la vela de la barrida o posterior, primera vela desde 2 antes) y lo
respeta (cierra por encima del borde inferior) → LARGO. Stop: borde inferior del FVG − 1 tick, o el máximo de Asia
(nivel barrido) − 1 tick. Objetivo: 1R o 2R. Se anula si antes cierra de nuevo dentro del rango de Asia.
Una operación al día. Regla de selección (antes de la prueba): esperanza > 0 en desarrollo Y validación (coste base), n_val >= 30.
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

A0, A1, W0, KZ_END, EXIT_K = 120, 360, 360, 660, 925


def _r(x):
    return round(x / TICK) * TICK


def signal(m, tf, stop_mode, target):
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[A0:A1]).sum() > (A1 - A0) / 2:
        return None
    ah, al = np.nanmax(H[A0:A1]), np.nanmin(L[A0:A1])
    if ah <= al:
        return None
    ks, b = [], []
    for k in range(W0, KZ_END, tf):
        ok = ~np.isnan(C[k:k + tf])
        if ok.any():
            ks.append(k)
            b.append((np.nanmax(H[k:k + tf]), np.nanmin(L[k:k + tf]), C[k:k + tf][ok][-1]))
    if len(b) < 4:
        return None
    h, l, c = (np.array(x) for x in zip(*b))
    isw = next((i for i in range(len(h)) if h[i] > ah or l[i] < al), None)
    if isw is None or (h[isw] > ah and l[isw] < al):
        return None
    side = -1 if h[isw] > ah else 1                    # barre el máximo → cortos
    # espacio "corto": para largos se invierte el signo
    xh, xl, xc = (h, l, c) if side == -1 else (-l, -h, -c)
    tgt_x = al if side == -1 else -ah                   # lado opuesto de Asia (en espacio corto)
    ext = xh[isw]
    fvg = None
    for t in range(isw + 1, len(c)):
        if fvg is not None and xh[t] >= fvg[0]:
            if xh[t] > ext:
                return None                             # supera el extremo de la barrida antes de entrar
            if xc[t] < fvg[1]:
                k_in = ks[t] + tf
                if k_in > KZ_END:
                    return None
                sx = (ext if stop_mode == "barrida" else fvg[1]) + TICK
                stop = sx if side == -1 else -sx
                if target == "asia":
                    tgt = tgt_x if side == -1 else -tgt_x
                    return Order(side, "market", k_in, _r(stop), _r(tgt), EXIT_K, tag="asia_fvg")
                return Order(side, "market", k_in, _r(stop), None, EXIT_K, target_r=2.0, tag="asia_fvg")
            fvg = None                                  # lo atraviesa con cierre: FVG invalidado
        if xh[t] > ext:
            ext = xh[t]
        if xl[t] <= tgt_x:
            return None                                 # ya llegó al objetivo sin señal
        if t - 2 >= isw and xh[t] < xl[t - 2]:
            fvg = (xh[t], xl[t - 2])
    return None


def signal_cont(m, tf, stop_mode, target):
    H, L, C = m[:, 1], m[:, 2], m[:, 3]
    if np.isnan(H[A0:A1]).sum() > (A1 - A0) / 2:
        return None
    ah, al = np.nanmax(H[A0:A1]), np.nanmin(L[A0:A1])
    if ah <= al:
        return None
    ks, b = [], []
    for k in range(W0, KZ_END, tf):
        ok = ~np.isnan(C[k:k + tf])
        if ok.any():
            ks.append(k)
            b.append((np.nanmax(H[k:k + tf]), np.nanmin(L[k:k + tf]), C[k:k + tf][ok][-1]))
    if len(b) < 4:
        return None
    h, l, c = (np.array(x) for x in zip(*b))
    isw = next((i for i in range(len(h)) if h[i] > ah or l[i] < al), None)
    if isw is None or (h[isw] > ah and l[isw] < al):
        return None
    side = 1 if h[isw] > ah else -1                     # barre el máximo → largos a favor
    # espacio "largo": para cortos se invierte el signo
    xh, xl, xc = (h, l, c) if side == 1 else (-l, -h, -c)
    lvl = ah if side == 1 else -al                      # nivel barrido en espacio largo
    fvg = None
    t0 = max(2, isw)
    if t0 >= 2 and isw >= 2 and xl[isw] > xh[isw - 2]:
        fvg = (xh[isw - 2], xl[isw])
    for t in range(isw + 1, len(c)):
        if xc[t] < lvl:
            return None                                 # vuelve a cerrar dentro del rango de Asia
        if fvg is not None and xl[t] <= fvg[1]:
            if xc[t] > fvg[0]:
                k_in = ks[t] + tf
                if k_in > KZ_END:
                    return None
                sx = (fvg[0] if stop_mode == "fvg" else lvl) - TICK
                stop = sx if side == 1 else -sx
                return Order(side, "market", k_in, _r(stop), None, EXIT_K,
                             target_r=1.0 if target == "1R" else 2.0, tag="asia_fvg_cont")
            fvg = None
        if t - 2 >= isw - 2 and xl[t] > xh[t - 2]:
            fvg = (xh[t - 2], xl[t])
    return None


def main():
    S = sessions()
    D = rome_days(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"GIRO · FVG {tf} min, stop {sm}, objetivo {tg}": (signal, dict(tf=tf, stop_mode=sm, target=tg))
                for tf, sm, tg in itertools.product((5, 15), ("barrida", "fvg"), ("asia", "2R"))}
    variants.update({f"CONTINUACIÓN · FVG {tf} min, stop {sm}, objetivo {tg}": (signal_cont, dict(tf=tf, stop_mode=sm,
                                                                                                    target=tg))
                     for tf, sm, tg in itertools.product((5, 15), ("fvg", "nivel_asia"), ("1R", "2R"))})
    exp = new_experiment("asia_barrida_fvg_londres")
    rows = []
    for name, (fn, p) in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                o = fn(m, **p)
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
                             hora_entrada=f"{int(o_.entry_k.median() // 60)}:{int(o_.entry_k.median() % 60):02d}",
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    b = res[res.coste == "base"]
    piv = b.pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    nval = b[b.periodo == "validacion"].set_index("variante").n
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0) & (nval.reindex(piv.index) >= 30)].index.tolist()
    write_manifest(exp, experimento="barrida de Asia (2-6 Italia) + FVG respetado en killzone de Londres", reglas=__doc__,
                   seleccionadas=sel, periodos={k: [str(a.date()), str(b_.date())] for k, (a, b_) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 70)
    print(b[["variante", "periodo", "n", "ops_año", "pf", "esperanza", "acierto", "R_medio", "R_bruto", "ic90_bajo",
             "ic90_alto", "riesgo_mediano", "top10_pct", "hora_entrada", "salidas"]].round(2).to_string(index=False))
    print("\nCoste alto:")
    print(res[res.coste == "alto"].pivot_table(index="variante", columns="periodo", values="esperanza",
                                                sort=False).round(2).to_string())
    print("\nSeleccionadas (dev>0 y val>0):", sel)
    print("→", exp)


if __name__ == "__main__":
    main()
