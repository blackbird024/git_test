"""Barrida de la sesión anterior + reversión en FVG de 1 min (estrategia "Robin Hood" del usuario).

Hipótesis nueva; reglas en strategies/sweep_fvg.py, fijadas antes de ver resultados. Se informan las 12 variantes
(2 niveles × 2 confirmaciones × 3 salidas) con los tres periodos del protocolo y los tres costes.
"""
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import run
from data.loaders import daily_from_sessions, nq_1m, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.sweep_fvg import sweep_fvg
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def overnight_levels(S):
    """Máximo y mínimo de 18:00 ET del día de mercado anterior a 9:29 ET de cada sesión (solo datos previos)."""
    df = nq_1m()
    out, prev = {}, None
    for s in S:
        if prev is not None:
            a = df.index.searchsorted(pd.Timestamp(f"{prev.date()} 18:00", tz="America/New_York"))
            b = df.index.searchsorted(pd.Timestamp(f"{s.date.date()} 09:30", tz="America/New_York"))
            if b - a > 30:
                x = df.iloc[a:b]
                out[s.date] = (x["high"].max(), x["low"].min())
        prev = s.date
    return out


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    for d, (h, l) in overnight_levels(S).items():
        if d in ctx:
            ctx[d] = {**ctx[d], "on_high": h, "on_low": l}
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    exp = new_experiment("sweep_fvg_robin_hood")
    rows = []
    variants = {f"{lv} {'conf15' if cf else 'sin_conf'} {ex}": dict(level=lv, confirm15=cf, exit=ex)
                for lv, cf, ex in itertools.product(("pdhl", "overnight"), (False, True), ("2R_1200", "2R_cierre", "cierre"))}
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            t = trades_frame(run(S, sweep_fvg, c, ctx=ctx, **p), c)
            if scen == "base":
                t.to_csv(exp / f"ops_{name.replace(' ', '_')}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                s = summary(tp, cals[k])
                rows.append(dict(variante=name, coste=scen, periodo=k, riesgo_mediano_usd=tp["risk_usd"].median(), **s))
            o = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o), esperanza=o.pnl.mean(),
                             pf=o.pnl[o.pnl > 0].sum() / -o.pnl[o.pnl < 0].sum(), ic90_bajo=lo, ic90_alto=hi,
                             acierto=(o.pnl > 0).mean(), riesgo_mediano_usd=o["risk_usd"].median()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="barrida sesión anterior + FVG 1 min", variantes=variants, sesiones=len(S),
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 250, "display.max_rows", 300)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "neto_año", "pf", "esperanza", "acierto", "ic90_bajo", "ic90_alto", "dd_max",
             "riesgo_mediano_usd"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
