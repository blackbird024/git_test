"""Paso 2: optimización secuencial (train optimiza, validation selecciona), walk-forward, sensibilidad, TEST FINAL
(una sola vez por configuración), escenarios de riesgo y Monte Carlo de las finalistas.

Uso: python optimize.py   -> results/optimization.pkl, optimization/*.csv, results/TEST_LOG.md
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import pickle
from datetime import datetime, timezone

import pandas as pd

from src.common import ROOT, labs_disponibles, load_config, params
from src.metrics import breakdowns
from src.monte_carlo import monte_carlo
from src.optimizer import secuencia
from src.walk_forward import walk_forward

REFERENCIA = {"NQ": "MNQ", "GC": "MGC"}


def huella(p: dict) -> str:
    return hashlib.sha1(json.dumps(p, sort_keys=True, default=str).encode()).hexdigest()[:10]


def sensibilidad(lab, p, cfg):
    s = cfg["search"]["sensitivity"]
    ema = []
    q0 = copy.deepcopy(p)
    if q0["model"] in ("A", "B"):
        q0["model"] = "C"                                      # para ver la zona de EMA50/200 aunque la final no la use
    for es, em in itertools.product(s["ema_slow"], s["ema_medium"]):
        q = dict(q0, ema_slow=es, ema_medium=em)
        m = lab.run(q, "train")[1]
        ema.append({"ema_slow": es, "ema_medium": em, "expectancy_R": m.get("expectancy_R"), "trades": m.get("trades")})
    atr = []
    for mult, per in itertools.product(s["atr_multiplier"], s["atr_period"]):
        q = dict(p, stop_type="atr", atr_multiplier=mult, atr_period=per)
        m = lab.run(q, "train")[1]
        atr.append({"atr_multiplier": mult, "atr_period": per, "expectancy_R": m.get("expectancy_R"), "trades": m.get("trades")})
    return {"modelo_usado_ema": q0["model"], "ema": pd.DataFrame(ema), "atr": pd.DataFrame(atr)}


def main() -> None:
    cfg = load_config()
    labs, faltan = labs_disponibles(cfg)
    log = ROOT / "results" / "TEST_LOG.md"
    registro = log.read_text(encoding="utf-8") if log.exists() else "# Registro de uso del TEST\n"
    out, finales = {"faltan": faltan, "instrumentos": {}}, {}
    (ROOT / "optimization").mkdir(exist_ok=True)
    primarios = [n for n in labs if cfg["instruments"][n].get("primary")]
    for nombre in primarios + [n for n in labs if n not in primarios]:
        lab = labs[nombre]
        print(f"\n=== {nombre} ===")
        res = {}
        p0 = params(cfg)
        if nombre in primarios:
            final, tabla, decisiones = secuencia(lab, cfg, p0)
            res.update(etapas=tabla, decisiones=decisiones)
            tabla.to_csv(ROOT / "optimization" / f"{nombre}_etapas.csv", index=False)
            print("decisiones:", decisiones)
            print("  walk-forward...")
            res["wf"], res["wf_trades"] = walk_forward(lab, final, cfg)
            print("  sensibilidad...")
            res["sens"] = sensibilidad(lab, final, cfg)
        else:
            final = finales.get(REFERENCIA[nombre], p0)            # referencia: misma configuración que su micro
        finales[nombre] = final
        res["final"] = final
        # TEST FINAL: una sola vez por (instrumento, configuración)
        configs_test = {"final": final, **{f"modelo {m} (baseline)": params(cfg, model=m) for m in cfg["search"]["models"]}}
        res["periodos"] = {}
        for etq, p in configs_test.items():
            clave = f"{nombre}:{etq}:{huella(p)}"
            primera = clave not in registro
            filas = {}
            for per in ("train", "validation", "test"):
                r, m = lab.run(p, per)
                filas[per] = (r, m)
            if primera:
                registro += f"- {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} `{clave}`\n"
            res["periodos"][etq] = filas
        # Riesgo y costes adversos (configuración final)
        res["riesgo"] = pd.DataFrame([{"risk_%": rp, "periodo": per, **{k: lab.run(dict(final, risk_per_trade=rp), per)[1].get(k)
                                        for k in ("trades", "net_pnl", "max_dd", "max_dd_%", "sharpe", "calmar")}}
                                      for rp in cfg["search"]["risk_levels"] for per in ("train", "validation", "test")])
        res["costes_x2"] = {per: lab.run(final, per, slippage_mult=2.0)[1] for per in ("train", "validation", "test")}
        # Monte Carlo y desgloses de la finalista
        mc = cfg["monte_carlo"]
        dev = pd.concat([res["periodos"]["final"]["train"][0].trades, res["periodos"]["final"]["validation"][0].trades])
        te = res["periodos"]["final"]["test"][0].trades
        res["mc"] = {"train+validation": monte_carlo(dev.net_pnl, lab.capital, mc["n"], cfg["general"]["seed"], mc["dd_thresholds_pct"]),
                     "test": monte_carlo(te.net_pnl, lab.capital, mc["n"], cfg["general"]["seed"], mc["dd_thresholds_pct"]) if len(te) else {}}
        res["desgloses"] = {"train+validation": breakdowns(dev, lab.inst) if len(dev) else {},
                            "test": breakdowns(te, lab.inst) if len(te) > 3 else {}}
        m_te = res["periodos"]["final"]["test"][1]
        print(f"  final: {final['model']}/{final['entry_type']}/{final['trend_filters']}/{final['stop_type']} {final['atr_multiplier']}/"
              f"TP {final['take_profit_R']}/{final['exit_type']}/{final['window']} -> TEST R {m_te.get('expectancy_R')} t {m_te.get('t_R')} PF {m_te.get('profit_factor')}")
        out["instrumentos"][nombre] = res
    log.write_text(registro, encoding="utf-8")
    (ROOT / "results" / "optimization.pkl").write_bytes(pickle.dumps(out))
    print("\nGuardado en results/optimization.pkl")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    main()
