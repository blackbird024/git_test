"""Walk-forward anclado por años: optimiza la rejilla de salidas en `train_years` años y aplica la elección al año
siguiente, avanzando de año en año. Solo usa train+validation (el test final no se toca aquí)."""
from __future__ import annotations

import pandas as pd

from .backtester import run
from .metrics import resumen
from .optimizer import elegir, rejilla
from .pipeline import variante


def walk_forward(b, sub, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    w = cfg["walk_forward"]
    filas, ops = [], []
    for anio in range(w["first_test_year"], w["last_test_year"] + 1):
        ini_tr, fin_tr = f"{anio - w['train_years']}-01-01", f"{anio - 1}-12-31"
        ini_te, fin_te = f"{anio}-01-01", f"{anio + w['test_years'] - 1}-12-31"
        tabla = rejilla(b, sub, cfg, ini_tr, fin_tr)
        mejor = elegir(tabla, cfg["optimization"]["min_trades"])
        if mejor is None:
            filas.append({"test": anio, "entrenamiento": f"{ini_tr}..{fin_tr}", "eleccion": "ninguna"})
            continue
        tp = None if mejor.tp_r == "sin" else float(mejor.tp_r)
        c = variante(cfg, **{"strategy.exits.sl_atr_mult": float(mejor.sl_atr_mult), "strategy.exits.tp_r": tp})
        r = run(b, sub, c, ini_te, fin_te)
        m = resumen(r.trades, r.daily, r.capital_inicial)
        filas.append({"test": anio, "entrenamiento": f"{ini_tr}..{fin_tr}", "sl_atr_mult": mejor.sl_atr_mult,
                      "tp_r": mejor.tp_r, "R_entrenamiento": mejor.expectativa_R,
                      **{k: m.get(k) for k in ("operaciones", "expectativa_R", "t_R", "profit_factor", "neto_usd")}})
        if len(r.trades):
            ops.append(r.trades.assign(wf_test=anio))
    return pd.DataFrame(filas), (pd.concat(ops) if ops else pd.DataFrame())
