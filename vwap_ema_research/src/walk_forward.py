"""Walk-forward anual dentro de train+validation (el test no se usa): con la configuración final, re-optimiza
stop (x ATR) y take profit en `train_years` años, elige por expectativa suavizada con las vecinas de la rejilla (zona
estable, no el máximo aislado) y aplica la elección al año siguiente."""
from __future__ import annotations

import copy
import itertools

import numpy as np
import pandas as pd

from .common import Lab


def _grid(lab: Lab, p: dict, desde, hasta, mults, tps):
    filas = []
    for m, tp in itertools.product(mults, tps):
        q = copy.deepcopy(p)
        q.update(stop_type="atr", atr_multiplier=m, take_profit_R=tp)
        s = lab.run(q, (desde, hasta))[1]
        filas.append({"atr_multiplier": m, "take_profit_R": "sin" if tp is None else tp, "expectancy_R": s.get("expectancy_R", np.nan), "trades": s.get("trades", 0)})
    return pd.DataFrame(filas)


def suavizar(t: pd.DataFrame) -> pd.DataFrame:
    piv = t.pivot(index="atr_multiplier", columns="take_profit_R", values="expectancy_R")
    s = piv.copy()
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            s.iloc[i, j] = np.nanmean(piv.iloc[max(0, i - 1):i + 2, max(0, j - 1):j + 2].to_numpy())
    t = t.copy()
    t["smoothed_R"] = [s.loc[a, b] for a, b in zip(t.atr_multiplier, t.take_profit_R)]
    return t


def walk_forward(lab: Lab, p: dict, cfg: dict):
    w, s = cfg["search"]["walk_forward"], cfg["search"]
    mults = sorted({m for st, m in s["stops"] if st == "atr"})
    tps = s["take_profits"]
    d0, d1 = lab.splits["dev"]
    filas, ops = [], []
    for anio in range(d0.year + w["train_years"], d1.year + 1):
        tr = (pd.Timestamp(f"{anio - w['train_years']}-01-01"), pd.Timestamp(f"{anio - 1}-12-31"))
        te = (pd.Timestamp(f"{anio}-01-01"), min(pd.Timestamp(f"{anio + w['test_years'] - 1}-12-31"), d1))
        g = suavizar(_grid(lab, p, *tr, mults, tps))
        g = g[g.trades >= 50]
        if g.empty:
            continue
        best = g.sort_values("smoothed_R", ascending=False).iloc[0]
        q = copy.deepcopy(p)
        q.update(stop_type="atr", atr_multiplier=best.atr_multiplier,
                 take_profit_R=None if best.take_profit_R == "sin" else float(best.take_profit_R))
        r, m = lab.run(q, te)
        filas.append({"año_test": anio, "entreno": f"{tr[0].date()}..{tr[1].date()}", "atr_multiplier": best.atr_multiplier,
                      "take_profit_R": best.take_profit_R, "R_entreno_suavizado": round(best.smoothed_R, 4),
                      **{k: m.get(k) for k in ("trades", "expectancy_R", "t_R", "profit_factor", "net_pnl")}})
        if len(r.trades):
            ops.append(r.trades.assign(wf_year=anio))
    return pd.DataFrame(filas), (pd.concat(ops, ignore_index=True) if ops else pd.DataFrame())
