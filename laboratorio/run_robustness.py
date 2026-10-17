"""Robustez de MNQ_ORB_RETEST_v1 (después del baseline). Uso, desde laboratorio/:

  python run_robustness.py --strategy MNQ_ORB_RETEST_v1

Rejilla completa tolerancia {1,2,4} ticks × ventana {1,2,3} velas × objetivo {1; 1,5; 2; 2,5} R con coste base,
hora límite {10:30, 11:30, 12:30}, los 5 escenarios de coste para el baseline y, como experimento SECUNDARIO, filtros
de anchura del rango (terciles fijados con desarrollo). La prueba solo se muestra si las reglas del baseline están
congeladas; nunca se usa para elegir. Salida: reports/MNQ_ORB_RETEST_v1/robustness.csv
"""
import argparse
import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from data.loaders import sessions
from orb_retest.config import BASELINE, COST_SCENARIOS, VERSION
from orb_retest.pipeline import FREEZE, OUT, PARTS, add_context, check_freeze, run_all
from validation.metrics import block_bootstrap_mean


def _dd(R):
    e = np.concatenate([[0], np.cumsum(R)])
    return float((e - np.maximum.accumulate(e)).min())


def summarize(t, name, params, include_test):
    row = dict(variante=name, **params)
    for p in PARTS:
        if p == "prueba" and not include_test:
            continue
        x = t[t.particion == p] if len(t) else t
        R = x.R.to_numpy() if len(x) else np.array([])
        usd = x.net_usd_1c.to_numpy() if len(x) else np.array([])
        gl = -usd[usd < 0].sum()
        row.update({f"{p}_ops": len(x), f"{p}_ER": R.mean() if len(R) else np.nan,
                    f"{p}_PF": usd[usd > 0].sum() / gl if gl > 0 else np.nan,
                    f"{p}_maxDD_R": _dd(R) if len(R) else np.nan,
                    f"{p}_acierto": (usd > 0).mean() if len(usd) else np.nan})
    oos = t[t.particion.isin(["validacion"] + (["prueba"] if include_test else []))] if len(t) else t
    lo, hi = block_bootstrap_mean(oos.R.to_numpy()) if len(oos) >= 20 else (np.nan, np.nan)
    row.update(fuera_ER=oos.R.mean() if len(oos) else np.nan, fuera_ops=len(oos), fuera_ic90_bajo=lo, fuera_ic90_alto=hi)
    if len(t):
        yr = t.groupby(t.date.dt.year).R.sum()
        row["años_positivos"] = f"{int((yr > 0).sum())}/{len(yr)}"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="MNQ_ORB_RETEST_v1")
    a = ap.parse_args()
    if not VERSION.startswith(a.strategy):
        raise SystemExit(f"Estrategia desconocida: {a.strategy}")
    include_test = FREEZE.exists()
    if include_test:
        check_freeze(BASELINE)
    S = sessions()
    rows = []
    # 1) rejilla completa con coste base
    for tol, win, tp in itertools.product((1, 2, 4), (1, 2, 3), (1.0, 1.5, 2.0, 2.5)):
        cfg = BASELINE.with_(tol_ticks=tol, retest_bars=win, tp_r=tp)
        t, _ = run_all(cfg, include_test, ["base"], S)["base"]
        base = (tol, win, tp) == (2, 3, 2.0)
        rows.append(summarize(t, "BASELINE" if base else "rejilla", dict(tol_ticks=tol, ventana=win, tp_r=tp,
                                                                         hora_limite="11:30", coste="base"), include_test))
    # 2) hora límite para nuevas entradas
    for k, hh in ((90, "11:00"), (60, "10:30"), (180, "12:30")):
        t, _ = run_all(BASELINE.with_(last_entry_k=k), include_test, ["base"], S)["base"]
        rows.append(summarize(t, "hora_limite", dict(tol_ticks=2, ventana=3, tp_r=2.0, hora_limite=hh, coste="base"),
                              include_test))
    # 3) costes y deslizamiento (baseline)
    res = run_all(BASELINE, include_test, None, S)
    for sc, (t, _) in res.items():
        rows.append(summarize(t, "coste", dict(tol_ticks=2, ventana=3, tp_r=2.0, hora_limite="11:30", coste=sc),
                              include_test))
    # 3b) objetivo que exige solo tocar (sin cruce) — supuesto de ejecución del TP menos conservador
    c_touch = replace(BASELINE, costs=replace(COST_SCENARIOS["base"], name="base_tp_toque", tp_cross_ticks=0))
    from orb_retest.engine import run as run_engine
    from orb_retest.pipeline import label
    t, _ = run_engine(S, c_touch)
    t["particion"] = label(t.date, c_touch)
    if not include_test:
        t = t[t.particion != "prueba"]
    rows.append(summarize(t, "tp_al_tocar", dict(tol_ticks=2, ventana=3, tp_r=2.0, hora_limite="11:30",
                                                 coste="base_tp_toque"), include_test))
    # 4) SECUNDARIO: filtros de anchura del rango (umbrales de desarrollo)
    t, _ = res["base"]
    t, thr = add_context(t, S)
    for terc in ("bajo", "medio", "alto"):
        x = t[t.or_width_pct_tercil == terc]
        rows.append(summarize(x, "secundario_anchura_OR_pct", dict(tol_ticks=2, ventana=3, tp_r=2.0, hora_limite="11:30",
                                                                coste="base", filtro=f"OR {terc}"), include_test))
    r = pd.DataFrame(rows)
    r.to_csv(OUT / "robustness.csv", index=False)
    g = r[r.variante.isin(["rejilla", "BASELINE"])]
    both = ((g.desarrollo_ER > 0) & (g.validacion_ER > 0)).sum()
    print(f"variantes probadas: {len(r)} (rejilla {len(g)}); positivas en desarrollo Y validación: {both}/{len(g)}")
    pd.set_option("display.width", 250)
    cols = ["variante", "tol_ticks", "ventana", "tp_r", "hora_limite", "coste", "desarrollo_ops", "desarrollo_ER",
            "validacion_ops", "validacion_ER"] + (["prueba_ops", "prueba_ER"] if include_test else []) + ["fuera_ER"]
    print(r[cols].round(3).to_string(index=False))
    print("→", OUT / "robustness.csv")


if __name__ == "__main__":
    main()
