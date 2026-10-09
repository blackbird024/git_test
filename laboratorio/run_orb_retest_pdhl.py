"""ORB 5 min con ruptura + retesteo y objetivo en el máximo/mínimo de ayer (PDH para largos, PDL para cortos).

Reglas de ruptura y retesteo idénticas a A1 retest (strategies/orb.py). Fijadas antes de ver resultados:
  objetivo = PDH/PDL (si ya está superado al entrar, no se opera); stop = vela de retesteo ± 1 tick
  sin alcanzar el objetivo: cierre a las 11:30 ET o a las 15:55 ET
  filtro de recorrido mínimo: ninguno o el objetivo a ≥ 1R
Referencia: el mismo retesteo con objetivo 2R (ya rechazado).
"""
import itertools

import pandas as pd

from backtests.intraday import run
from data.loaders import daily_from_sessions, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.orb import orb
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"PDH/PDL salida {ex} minR {mr}": dict(variant="retest", stop_mode="rango", exit=ex, target="pdhl", min_r=mr)
                for ex, mr in itertools.product(("2R_1130", "eod"), (0.0, 1.0))}
    variants["referencia 2R salida 11:30"] = dict(variant="retest", stop_mode="rango", exit="2R_1130")
    exp = new_experiment("orb_retest_pdhl")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, orb, c, ctx=ctx, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                s = summary(tp, cals[k])
                rows.append(dict(variante=name, coste=scen, periodo=k, **s))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rr = ((o.target - o.entry).abs() / o.risk_pts).median() if "target" in o and len(o) else float("nan")
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), ic90_bajo=lo, ic90_alto=hi,
                             acierto=(o.pnl > 0).mean(), R_objetivo_mediano=rr,
                             pct_llega_objetivo=(o.reason == "objetivo").mean()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="ORB retest con objetivo PDH/PDL", variantes=variants,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 250, "display.max_rows", 200)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "neto_año", "pf", "esperanza", "acierto", "ic90_bajo", "ic90_alto",
             "R_objetivo_mediano", "pct_llega_objetivo", "dd_max"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
