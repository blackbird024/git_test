"""Backtest de MNQ_ORB_RETEST_v1 (baseline). Uso, desde laboratorio/:

  python run_backtest.py --strategy MNQ_ORB_RETEST_v1              # solo desarrollo + validación
  python run_backtest.py --strategy MNQ_ORB_RETEST_v1 --congelar   # congela las reglas actuales (FREEZE.json)
  python run_backtest.py --strategy MNQ_ORB_RETEST_v1 --abrir-prueba   # añade la prueba (exige reglas congeladas)

Salida en reports/MNQ_ORB_RETEST_v1/.
"""
import argparse
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from data.loaders import sessions
from orb_retest.config import BASELINE, COST_SCENARIOS, VERSION
from orb_retest.pipeline import (OUT, add_context, breakdowns, check_freeze, freeze, git_rev, metrics_table, run_all,
                                 sized_runs)


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (pd.Timestamp,)):
        return str(o)
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="MNQ_ORB_RETEST_v1")
    ap.add_argument("--congelar", action="store_true")
    ap.add_argument("--abrir-prueba", action="store_true")
    a = ap.parse_args()
    if not VERSION.startswith(a.strategy):
        raise SystemExit(f"Estrategia desconocida: {a.strategy} (disponible: {VERSION})")
    cfg = BASELINE
    OUT.mkdir(parents=True, exist_ok=True)
    if a.congelar:
        f = freeze(cfg)
        print("Reglas congeladas:", f["strategy_hash"], "git", f["git"])
        return
    frz = check_freeze(cfg) if a.abrir_prueba else None
    S = sessions()
    res = run_all(cfg, include_test=a.abrir_prueba, S=S)
    t, days = res["base"]
    t, thr = add_context(t, S)
    sized = sized_runs(t)
    metrics = {sc: metrics_table(*res[sc], cfg, sized[50] if sc == "base" else None) for sc in res}
    sized_m = {b: {p: dict(neto_usd=float(z[z.particion == p].pnl_usd.sum()),
                           contratos_medios=float(z[(z.particion == p) & (z.contracts > 0)].contracts.mean()),
                           ops_sin_contrato=int(((z.particion == p) & (z.skipped == "no_cabe_un_contrato")).sum()))
                   for p in z.particion.unique()} for b, z in sized.items()}
    conf = dict(version=VERSION, git=git_rev(), strategy_hash=cfg.strategy_hash(), prueba_abierta=a.abrir_prueba,
                congelacion=frz, config=asdict(cfg), escenarios_coste={k: asdict(v) for k, v in COST_SCENARIOS.items()},
                umbrales_terciles_desde_desarrollo=thr, ejecutado=pd.Timestamp.now().isoformat(timespec="seconds"))
    (OUT / "backtest_config.json").write_text(json.dumps(conf, indent=2, ensure_ascii=False, default=_json))
    (OUT / "metrics.json").write_text(json.dumps(dict(por_escenario_de_coste=metrics, tamano_por_riesgo=sized_m),
                                                 indent=2, ensure_ascii=False, default=_json))
    z50 = sized[50][["date", "contracts", "pnl_usd", "skipped"]].rename(
        columns=dict(contracts="contratos_riesgo50", pnl_usd="pnl_usd_riesgo50", skipped="omitida_riesgo50"))
    tt = t.merge(z50, on="date", how="left")
    tt.to_csv(OUT / "trades.csv", index=False)
    daily = days.merge(tt[["date", "R", "net_usd_1c", "pnl_usd_riesgo50", "reason"]], on="date", how="left")
    daily[["R", "net_usd_1c", "pnl_usd_riesgo50"]] = daily[["R", "net_usd_1c", "pnl_usd_riesgo50"]].fillna(0.0)
    daily.to_csv(OUT / "daily_results.csv", index=False)
    for freq, name in (("M", "monthly_results.csv"), ("Y", "yearly_results.csv")):
        g = daily.groupby([daily.date.dt.to_period(freq), "particion"])
        x = pd.DataFrame(dict(sesiones=g.size(), operaciones=g.motivo.apply(lambda s: (s == "operacion").sum()),
                              ganadoras=g.net_usd_1c.apply(lambda s: (s > 0).sum()), R=g.R.sum(),
                              neto_usd_1c=g.net_usd_1c.sum(), neto_usd_riesgo50=g.pnl_usd_riesgo50.sum()))
        x.reset_index().rename(columns=dict(date="periodo")).to_csv(OUT / name, index=False)
    for k, df in breakdowns(t).items():
        df.to_csv(OUT / f"desglose_{k}.csv", index=False)
    for sc, (ts, _) in res.items():
        if sc != "base":
            ts.to_csv(OUT / f"trades_coste_{sc}.csv.gz", index=False)
    m = metrics["base"]
    for p, v in m.items():
        print(f"{p:24s} ops {v.get('operaciones', 0):4d}  acierto {v.get('acierto', float('nan')):.2f}  "
              f"E[R] {v.get('esperanza_R', float('nan')):+.3f}  IC90 {v.get('ic90_R')}  PF {v.get('profit_factor', float('nan')):.2f}  "
              f"maxDD {v.get('max_dd_R', float('nan')):.1f}R")
    print("→", OUT)


if __name__ == "__main__":
    main()
