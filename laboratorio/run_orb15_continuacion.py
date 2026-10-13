"""Candidato del estudio "gira o continúa" (run_orb_rev_vs_cont_todas.py, hallazgo A POSTERIORI entre 57 ventanas):
ruptura A FAVOR del rango de la vela de 15 min de 8:15-8:30 ET (14:15 Italia; termina con los datos macro de las 8:30)
y de 9:15-9:30 ET (15:15 Italia; termina en la apertura de NY). MNQ. Reglas fijadas ANTES de ver resultados:
1. Rango: máximo y mínimo de la vela de 15 min.
2. Entrada: orden stop 1 tick fuera del rango en el lado que rompe primero (OCO). Si rompe los dos lados en el mismo
   minuto, no se opera. Una operación al día por ventana.
3. Stop: el otro lado del rango ∓ 1 tick.
4. Objetivo (variantes): nivel roto + 1 × rango (distancias iguales, como la estadística) o sin objetivo.
5. Plazo: 3,5 h tras cerrar el rango (12:00 ET para 8:15; 13:00 ET para 9:15). Salida a mercado.
Costes: base, alto y alto + 4 ticks extra de deslizamiento por lado (minutos de dato/apertura).
Regla de selección: esperanza > 0 en desarrollo Y validación (coste base), n_val >= 30.
AVISO: la ventana se eligió mirando 2018-2026 entero; la prueba 2025-26 no es virgen.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import Order, simulate
from data.loaders import TICK, sessions
from execution_costs.costs import mnq
from run_orb_ventanas_edgeful import NE, et_days, first_breaks
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest

WINS = {"8:15 ET (14:15 Italia)": 495, "9:15 ET (15:15 Italia)": 555}


def order(m, a, target):
    ex = min(a + 15 + 210, 955)
    r = first_breaks(m, a)
    if r is None:
        return None, ex
    hi, lo, ku, kd = r
    R = hi - lo
    cand = [(k, s) for k, s in ((ku, 1), (kd, -1)) if k is not None and k < ex]
    if R <= 0 or not cand or (ku is not None and ku == kd):
        return None, ex
    k, side = min(cand)
    lvl = hi + TICK if side == 1 else lo - TICK
    stop = lo - TICK if side == 1 else hi + TICK
    tgt = (hi + R) if side == 1 else (lo - R)
    return Order(side, "stop", k, stop, tgt if target == "1rango" else None, ex, level=lvl, k_last=k + 1,
                 tag="orb15_cont"), ex


def main():
    D = et_days(sessions())
    per = periods("intradia", include_test=True)
    cal = pd.DatetimeIndex([d for d, _ in D])
    cals = calendar_split(cal, per)
    exp = new_experiment("orb15_continuacion")
    costs = {"base": mnq("base"), "alto": mnq("alto"), "alto+4ticks": mnq("alto", extra_slip_ticks=4)}
    rows = []
    for (wn, a), tg in itertools.product(WINS.items(), ("1rango", "sin_objetivo")):
        name = f"{wn}, objetivo {tg}"
        for cn, c in costs.items():
            fills = []
            for date, m in D:
                o, ex = order(m, a, tg)
                if o is not None:
                    f = simulate(date, m, ex + 1, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if cn == "base":
                t.to_csv(exp / f"ops_{a}_{tg}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=cn, periodo=k, **summary(tp, cals[k], minutes_per_session=NE)))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            srt = o_.pnl.sort_values(ascending=False)
            rows.append(dict(variante=name, coste=cn, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             R_bruto=(o_.gross_pts * 2 / o_.risk_usd).mean(), ic90_bajo=lo, ic90_alto=hi,
                             riesgo_mediano=o_.risk_usd.median(),
                             top10_pct=100 * srt[:10].sum() / o_.pnl.sum() if o_.pnl.sum() > 0 else np.nan,
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
            if cn == "base":
                y = t.groupby(t.date.dt.year).pnl.sum().round(0)
                rows.append(dict(variante=name, coste=cn, periodo="por_año", **{str(k): v for k, v in y.items()}))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    b = res[(res.coste == "base") & res.periodo.isin(["desarrollo", "validacion", "prueba"])]
    piv = b.pivot_table(index="variante", columns="periodo", values="esperanza", sort=False)
    nv = b[b.periodo == "validacion"].set_index("variante").n.reindex(piv.index)
    sel = piv[(piv.desarrollo > 0) & (piv.validacion > 0) & (nv >= 30)].index.tolist()
    write_manifest(exp, experimento="ORB 15 min a favor: 8:15 y 9:15 ET", reglas=__doc__, seleccionadas=sel,
                   periodos={k: [str(x.date()), str(y_.date())] for k, (x, y_) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 100, "display.max_colwidth", 70)
    for cn in costs:
        print(f"\n== coste {cn} ==")
        x = res[(res.coste == cn) & (res.periodo != "por_año")]
        print(x[["variante", "periodo", "n", "pf", "esperanza", "acierto", "R_bruto", "ic90_bajo", "ic90_alto",
                 "dd_max", "riesgo_mediano", "top10_pct", "salidas"]].round(2).to_string(index=False))
    print("\nNeto por año (coste base):")
    print(res[res.periodo == "por_año"].drop(columns=["coste", "periodo"]).dropna(axis=1, how="all").set_index("variante")
          .round(0).to_string())
    print("\nSeleccionadas (dev>0, val>0, n_val>=30):", sel)
    print("→", exp)


if __name__ == "__main__":
    main()
