"""Sensibilidad (vecindad pre-registrada en cada módulo) y estabilidad de parámetros (CRITERIOS.md §6).

Estabilidad = media de 4 fracciones: vecinos con expectativa > 0, años positivos, regímenes de volatilidad positivos
(de los que tienen ≥ 10 operaciones) y costes ×2 positivos (0 o 1). Se busca una meseta, no un pico.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import metricas as M


def vecindad(mod, ctx, params: dict, filtro_ops) -> pd.DataFrame:
    filas = {"(elegida)": {**M.rapidas(filtro_ops(mod.ejecutar(ctx, params)))}}
    for nombre, p in mod.vecindad(params).items():
        filas[nombre] = M.rapidas(filtro_ops(mod.ejecutar(ctx, p)))
    return pd.DataFrame(filas).T


def estabilidad(tabla_vecindad: pd.DataFrame, anual: dict, por_vol: pd.DataFrame, exp_x2: float) -> dict:
    vec = tabla_vecindad.drop(index="(elegida)", errors="ignore")
    f_vec = float((pd.to_numeric(vec["expectativa_$"]) > 0).mean()) if len(vec) else np.nan
    f_anio = float(np.mean([v > 0 for v in anual.values()])) if anual else np.nan
    pv = por_vol[por_vol.operaciones >= 10] if len(por_vol) else por_vol
    pv = pv.drop(index="sin dato", errors="ignore")
    f_vol = float((pv["expectativa_$"] > 0).mean()) if len(pv) else np.nan
    f_cost = 1.0 if exp_x2 > 0 else 0.0
    partes = [f_vec, f_anio, f_vol, f_cost]
    return {"vecinos_positivos": round(f_vec, 2), "años_positivos": round(f_anio, 2),
            "regimenes_vol_positivos": round(f_vol, 2), "costes_x2_positivo": f_cost,
            "estabilidad": round(float(np.nanmean(partes)), 2)}
