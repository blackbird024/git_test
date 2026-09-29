"""Búsqueda acotada de parámetros de salida (rejilla pequeña fijada en settings.yaml antes de ver resultados).

Criterio de elección (no el beneficio máximo): expectativa neta en R de la combinación, suavizada con la media de sus
vecinas en la rejilla (premia zonas estables, no picos aislados), exigiendo un mínimo de operaciones.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .backtester import run
from .metrics import resumen
from .pipeline import variante


def rejilla(b, sub, cfg: dict, desde, hasta) -> pd.DataFrame:
    o = cfg["optimization"]
    filas = []
    for sl, tp in itertools.product(o["sl_atr_mult"], o["tp_r"]):
        c = variante(cfg, **{"strategy.exits.sl_atr_mult": sl, "strategy.exits.tp_r": tp})
        r = run(b, sub, c, desde, hasta)
        m = resumen(r.trades, r.daily, r.capital_inicial)
        filas.append({"sl_atr_mult": sl, "tp_r": "sin" if tp is None else tp, **{k: m.get(k) for k in
                      ("operaciones", "expectativa_R", "t_R", "profit_factor", "neto_usd", "max_dd_usd")}})
    return pd.DataFrame(filas)


def elegir(tabla: pd.DataFrame, min_trades: int) -> pd.Series | None:
    t = tabla.copy()
    piv = t.pivot(index="sl_atr_mult", columns="tp_r", values="expectativa_R")
    suav = piv.copy()
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            suav.iloc[i, j] = np.nanmean(piv.iloc[max(0, i - 1):i + 2, max(0, j - 1):j + 2].to_numpy())
    t["R_suavizado"] = [suav.loc[a, b] for a, b in zip(t.sl_atr_mult, t.tp_r)]
    t = t[t.operaciones >= min_trades]
    if t.empty:
        return None
    return t.sort_values("R_suavizado", ascending=False).iloc[0]
