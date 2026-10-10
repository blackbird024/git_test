"""Backtest del CRT 4 h (strategies/crt.py) en NQ/MNQ 2018-2026. 4 variantes fijadas antes de ver resultados."""
import itertools

import pandas as pd

from backtests.intraday import simulate
from data.loaders import daily_from_sessions, sessions
from execution_costs.costs import mnq
from run_video_sweep_ob import days24
from strategies.crt import crt
from strategies.features import daily_context
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import calendar_split, new_experiment, periods, split, write_manifest


def main():
    S = sessions()
    ctx = daily_context(daily_from_sessions(S))
    D = days24(S)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test=True)
    cals = calendar_split(cal, per)
    variants = {f"{e}, objetivo {t}": dict(entry=e, target=t) for e, t in itertools.product(("clasica", "cisd"), ("rango", "2R"))}
    exp = new_experiment("crt_4h")
    rows = []
    for name, p in variants.items():
        for scen in ("bajo", "base", "alto"):
            c = mnq(scen)
            fills = []
            for d in D:
                o = crt(d, ctx, **p)
                if o is not None:
                    f = simulate(d["date"], d["sess"].m, d["sess"].close_min, o, c)
                    if f is not None:
                        fills.append(f)
            t = trades_frame(fills, c)
            if scen == "base":
                t.to_csv(exp / f"ops_{''.join(ch if ch.isalnum() else '_' for ch in name)}.csv.gz", index=False)
            for k, tp in split(t, per).items():
                rows.append(dict(variante=name, coste=scen, periodo=k, **summary(tp, cals[k])))
            o_ = t[t.date >= "2022-01-01"]
            lo, hi = block_bootstrap_mean(o_.pnl.to_numpy())
            rows.append(dict(variante=name, coste=scen, periodo="FM 2022-2026", n=len(o_), esperanza=o_.pnl.mean(),
                             pf=o_.pnl[o_.pnl > 0].sum() / -o_.pnl[o_.pnl < 0].sum(), acierto=(o_.pnl > 0).mean(),
                             ic90_bajo=lo, ic90_alto=hi, riesgo_mediano=o_.risk_usd.median(),
                             salidas=o_.reason.value_counts(normalize=True).round(2).to_dict()))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    write_manifest(exp, experimento="CRT 4h (C1 5-9 ET, C2 9-13 ET)", variantes=variants,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()})
    pd.set_option("display.width", 260, "display.max_rows", 200, "display.max_colwidth", 80)
    b = res[res.coste == "base"]
    print(b[["variante", "periodo", "n", "neto_año", "pf", "esperanza", "acierto", "ic90_bajo", "ic90_alto", "dd_max",
             "riesgo_mediano", "salidas"]].round(2).to_string(index=False))
    print("→", exp)


if __name__ == "__main__":
    main()
