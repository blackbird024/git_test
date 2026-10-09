"""Sistema A (intradía MNQ): ORB 5 min, continuación de tendencia y zona de ruido.

Fase de desarrollo + validación. La prueba final NO se calcula aquí (--prueba solo con reglas congeladas).

Uso:
    python run_sistema_a.py               # desarrollo y validación
    python run_sistema_a.py --prueba      # añade la prueba final (solo tras congelar reglas)
"""
import argparse
import itertools

import numpy as np
import pandas as pd

from backtests.intraday import run
from data.loaders import SRC, daily_from_sessions, sessions
from execution_costs.costs import mnq
from strategies.features import daily_context
from strategies.noise import noise_trades
from strategies.orb import orb
from strategies.trend import trend
from validation.metrics import block_bootstrap_mean, summary, trades_frame
from validation.runner import (calendar_split, file_fingerprint, new_experiment, periods, split,
                               write_manifest)

COLS = ["n", "ops_año", "neto_año", "pf", "esperanza", "acierto", "ratio_gp", "dd_max", "sharpe", "años_pos",
        "top10_ops_pct", "racha_perdedora"]


def variants():
    v = {}
    for var, st, ex in itertools.product(("immediate", "close", "retest"), ("rango", "vol"), ("2R_1130", "eod")):
        tag = "principal" if (st == "rango" and ex == "2R_1130") else "secundaria"
        v[f"A1 ORB {var} stop={st} salida={ex}"] = (orb, dict(variant=var, stop_mode=st, exit=ex), tag)
    for var in ("immediate", "close", "retest"):
        for f in ("trend", "vol"):
            v[f"A1 ORB {var} principal + filtro {f}"] = (orb, dict(variant=var, **{f: True}), "filtro")
    v["A2 Tendencia base"] = (trend, {}, "principal")
    for f in ("ema200", "vwap", "vol"):
        v[f"A2 Tendencia + filtro {f}"] = (trend, {f: True}, "filtro")
    v["A3 Zona de ruido (reglas originales)"] = ("noise", {}, "auditoria")
    return v


def run_variant(S, ctx, f, params, cost):
    if f == "noise":
        return noise_trades(S, cost, **params)
    return run(S, f, cost, ctx=ctx, **params)


def main(include_test=False, only=None):
    S = sessions()
    daily = daily_from_sessions(S)
    ctx = daily_context(daily)
    cal = pd.DatetimeIndex([s.date for s in S])
    per = periods("intradia", include_test)
    cals = calendar_split(cal, per)
    exp = new_experiment("sistema_a" + ("_con_prueba" if include_test else ""))
    rows, trades_all = [], {}
    for name, (f, params, tag) in variants().items():
        if only and only not in name:
            continue
        for scen in ("bajo", "base", "alto"):
            cost = mnq(scen)
            t = trades_frame(run_variant(S, ctx, f, params, cost), cost)
            if scen == "base":
                trades_all[name] = t
            parts = split(t, per) if len(t) else {k: t for k in per}
            for k, tp in parts.items():
                s = summary(tp, cals[k])
                lo, hi = block_bootstrap_mean(tp["pnl"].to_numpy()) if len(tp) else (np.nan, np.nan)
                rows.append(dict(estrategia=name, tipo=tag, coste=scen, periodo=k, ic90_bajo=lo, ic90_alto=hi,
                                 **{c: s.get(c, np.nan) for c in COLS}))
        print(name, "ok", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(exp / "resultados.csv", index=False)
    for name, t in trades_all.items():
        if len(t):
            t.assign(estrategia=name).to_csv(exp / f"ops_{_slug(name)}.csv.gz", index=False)
    write_manifest(exp, experimento="sistema_a", incluye_prueba=include_test,
                   datos=[file_fingerprint(SRC / "databento_nq_1m_2018_2024.pkl"),
                          file_fingerprint(SRC / "databento_glbx_1m.pkl")],
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()},
                   costes={s: mnq(s).__dict__ for s in ("bajo", "base", "alto")},
                   variantes={k: dict(params=v[1], tipo=v[2]) for k, v in variants().items()},
                   semilla_bootstrap=7, bloque_bootstrap=10, sesiones=len(S))
    print("→", exp)
    return res, exp


def _slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")[:80]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true")
    ap.add_argument("--solo")
    a = ap.parse_args()
    res, exp = main(a.prueba, a.solo)
    pd.set_option("display.width", 250, "display.max_rows", 500)
    b = res[res.coste == "base"]
    print(b[["estrategia", "periodo", "n", "neto_año", "pf", "esperanza", "ic90_bajo", "dd_max", "años_pos"]]
          .round(2).to_string(index=False))
