"""Ruptura del rango de una vela de 4 h (hora de Italia) en velas de 5 min, idea del usuario. NQ/MNQ.
Reglas fijadas ANTES de ver resultados:

- Vela "Londres": 0:00-4:00 Italia (= 18:00-22:00 ET del día anterior, la primera vela de 4 h de Globex).
  Rupturas de 4:00 a 12:00 Italia; cierre forzoso a las 15:25 Italia (antes de la apertura de NY).
- Vela "NY": 8:00-12:00 Italia (≈ 2:00-6:00 ET; corrección del usuario: "la de las 0:00 y la de las 8am").
  Rupturas (variantes) desde las 12:00 Italia, o solo desde la apertura de NY (9:30 ET, normalmente 15:30 Italia),
  hasta las 19:00 Italia; cierre forzoso 5 min antes del cierre de NY.
  (Una primera ejecución usó por error la vela 12:00-16:00: experimento 20261012_152307, se conserva.)
- Ruptura CON CUERPO (no vale solo la mecha): la primera vela de 5 min (alineada a la hora de Italia) cuyo cuerpo rompe.
  Variantes: "cierre" = el cierre queda por encima del máximo de la vela de 4 h (largo) / debajo del mínimo (corto);
  "cuerpo entero" = apertura Y cierre de la vela de 5 min fuera del rango (vela completamente fuera). Entrada a mercado en la apertura de la vela siguiente. Una operación por vela.
- Stop (variantes): mitad del rango de la vela de 4 h, o el extremo opuesto (± 1 tick).
- Objetivo (variantes): 1R o 2R.
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

CANDLES = {"Londres (vela 0:00-4:00)": (0, 12 * 60, 15 * 60 + 25, None),
           "NY (vela 8:00-12:00) desde 12:00": (8, 19 * 60, None, None),
           "NY (vela 8:00-12:00) desde apertura NY": (8, 19 * 60, None, "ny")}


def signal(m, cm, c_start, last_sig, exit_k, stop_mode, rr, body="cierre", start=None):
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    a, b = c_start * 60, c_start * 60 + 240
    if np.isnan(H[a:b]).sum() > 120:
        return None
    hi, lo = np.nanmax(H[a:b]), np.nanmin(L[a:b])
    if hi <= lo:
        return None
    ex = cm if exit_k is None else min(exit_k, cm)
    k0 = b if start is None else max(b, start)
    for k in range(k0, min(last_sig, ex), 5):
        x = C[k:k + 5]
        ok = ~np.isnan(x)
        if not ok.any():
            continue
        c = x[ok][-1]
        o = O[k:k + 5][ok][0]
        if body == "cierre":
            side = 1 if c > hi else -1 if c < lo else 0
        else:
            side = 1 if min(o, c) > hi else -1 if max(o, c) < lo else 0
        if side == 0:
            continue
        if stop_mode == "mitad":
            stop = round((hi + lo) / 2 / TICK) * TICK
        else:
            stop = lo - TICK if side == 1 else hi + TICK
        return Order(side, "market", k + 5, stop, None, ex, target_r=rr, tag="rango4h")
    return None


def main():
    S = sessions()
    D = rome_days(S)
    nyopen = {}
    for date, _, _ in D:
        d = date.date()
        t0 = pd.Timestamp(f"{d} 00:00", tz="Europe/Rome")
        k = int((pd.Timestamp(f"{d} 09:30", tz="America/New_York") - t0).total_seconds() // 60)
        nyopen[date] = k - k % 5
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {}
    for (cn, (cs, ls, xk, st)), bd, sm, rr in itertools.product(CANDLES.items(), ("cierre", "cuerpo entero"),
                                                            ("mitad", "opuesto"), (1.0, 2.0)):
        variants[f"{cn}, {bd}, stop {sm}, {rr:g}R"] = dict(c_start=cs, last_sig=ls, exit_k=xk, stop_mode=sm, rr=rr,
                                                           body=bd, start=st)
    exp = new_experiment("ruptura_4h_italia")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for date, m, cm in D:
                q = dict(p)
                if q["start"] == "ny":
                    q["start"] = nyopen[date]
                o = signal(m, cm, **q)
                if o is not None:
                    f = simulate(date, m, cm, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k], minutes_per_session=N)))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             R_medio=o_.R.mean(), R_bruto=(o_.gross_pts * 2 / o_.risk_usd).mean(), ic90_bajo=lo,
                             ic90_alto=hi, riesgo_mediano=o_.risk_usd.median(),
                             hora_entrada_mediana=f"{int(o_.entry_k.median() // 60)}:{int(o_.entry_k.median() % 60):02d}",
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="ruptura en 5 min del rango de una vela de 4 h (hora Italia)", reglas=__doc__,
                   variantes=variants, periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 280, "display.max_rows", 200, "display.max_colwidth", 70)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "pf", "esperanza", "acierto", "R_medio", "R_bruto", "ic90_bajo", "ic90_alto",
             "dd_max", "riesgo_mediano", "hora_entrada_mediana", "salidas"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
