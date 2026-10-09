"""Sistema B (swing 1-4 semanas) sobre QQQ diario ajustado (proxy del Nasdaq-100 con dividendos).

Uso:
    python run_sistema_b.py             # desarrollo y validación
    python run_sistema_b.py --prueba    # añade la prueba final (solo con reglas congeladas)
"""
import argparse

import numpy as np
import pandas as pd

from backtests.swing import SwingCost, equity, simulate, stats
from data.loaders import CACHE, etf_daily
from execution_costs.costs import load_yaml
from strategies.swing import SWING
from validation.runner import file_fingerprint, new_experiment, periods, write_manifest

LAST = "2026-10-08"          # la vela del 2026-10-09 estaba incompleta al descargar


def cost_scenarios():
    q = load_yaml()["QQQ_ETF_proxy"]
    pct = q["spread_y_slippage_pct_por_lado"] / 100
    fixed = q["comision_por_operacion_eur"]
    return {"capital 10k": SwingCost(pct, fixed, 10_000), "capital 2k": SwingCost(pct, fixed, 2_000),
            "capital 10k coste x2": SwingCost(2 * pct, 2 * fixed, 10_000)}


def main(include_test=False):
    d = etf_daily("QQQ", adjusted=True, last=LAST)
    per = periods("swing", include_test)
    rows, all_trades = [], []
    for name, (fn, p) in SWING.items():
        sig = fn(d, **p)
        for mode in ("next_open", "close"):
            for cname, cost in cost_scenarios().items():
                t = simulate(d, sig, cost, mode)
                for k, (a, b) in per.items():
                    tk = t[(t.entrada >= a) & (t.entrada <= b)]
                    eq, inpos = equity(d, tk, a, b)
                    rows.append(dict(estrategia=name, ejecucion=mode, coste=cname, periodo=k, **stats(eq, inpos, tk)))
                if cname == "capital 10k":
                    all_trades.append(t.assign(estrategia=name, ejecucion=mode))
    for k, (a, b) in per.items():
        x = d.loc[a:b, "close"]
        eq = x / x.iloc[0]
        st = stats(eq, pd.Series(True, index=eq.index), pd.DataFrame())
        rows.append(dict(estrategia="Benchmark comprar y mantener QQQ", ejecucion="-", coste="sin costes", periodo=k, **st))
    res = pd.DataFrame(rows)
    exp = new_experiment("sistema_b" + ("_con_prueba" if include_test else ""))
    res.to_csv(exp / "resultados.csv", index=False)
    pd.concat(all_trades).to_csv(exp / "operaciones.csv", index=False)
    write_manifest(exp, experimento="sistema_b", incluye_prueba=include_test,
                   datos=[file_fingerprint(CACHE / "QQQ_daily_adj.pkl")], ultima_fecha=LAST,
                   periodos={k: [str(a.date()), str(b.date())] for k, (a, b) in per.items()},
                   costes={k: v.__dict__ for k, v in cost_scenarios().items()},
                   estrategias={k: str(v[1]) for k, v in SWING.items()})
    return res, exp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true")
    a = ap.parse_args()
    res, exp = main(a.prueba)
    pd.set_option("display.width", 250, "display.max_rows", 500)
    b = res[(res.coste.isin(["capital 10k", "sin costes"]))]
    print(b[["estrategia", "ejecucion", "periodo", "n", "cagr", "dd_max_pct", "mar", "pf", "esperanza_pct",
             "exposicion", "dur_mediana", "pct_en_1_4_semanas"]].round(3).to_string(index=False))
    print("→", exp)
