"""Correlaciones entre bots y carteras A/B/C (CRITERIOS.md §9). P&L diario por sesión (día NY de salida), 1 MNQ por
unidad de peso, capital fijo sin reinversión."""
from __future__ import annotations

import numpy as np
import pandas as pd


def matriz(diarios: pd.DataFrame) -> dict:
    mes = diarios.resample("ME").sum()
    eq = diarios.cumsum()
    dd = eq - eq.cummax()
    return {"diaria": diarios.corr().round(3), "mensual": mes.corr().round(3), "drawdown": dd.corr().round(3)}


def evaluar(p: pd.Series, capital: float) -> dict:
    eq = p.cumsum()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq.to_numpy()])[1:]
    anual = p.groupby(p.index.year).sum()
    anios = len(p) / 252
    sd = p.std()
    return {"neto_$": round(p.sum(), 0), "neto_anual_$": round(p.sum() / anios, 0),
            "rentabilidad_anual_%": round(p.sum() / anios / capital * 100, 2),
            "volatilidad_anual_%": round(sd * np.sqrt(252) / capital * 100, 2),
            "sharpe": round(p.mean() / sd * np.sqrt(252), 2) if sd > 0 else np.nan,
            "max_dd_$": round(dd.min(), 0), "max_dd_%": round(dd.min() / capital * 100, 1),
            "peor_dia_$": round(p.min(), 0), "años_positivos": f"{int((anual > 0).sum())}/{len(anual)}",
            "neto/|DD|": round(p.sum() / -dd.min(), 2) if dd.min() < 0 else np.inf}


def elegir_nuevas(candidatas: list[tuple[str, float]], diarios: pd.DataFrame, base_cols: list[str],
                  corr_max: float, maximo: int = 3) -> list[str]:
    """candidatas: (nombre, puntuación) ordenadas de mejor a peor. B = la mejor; C = la siguiente con correlación
    diaria < corr_max con todas las ya incluidas (incluidas las de la cartera A)."""
    elegidas = []
    for nombre, _ in candidatas:
        if len(elegidas) >= maximo:
            break
        dentro = base_cols + elegidas
        if not elegidas or all(abs(diarios[nombre].corr(diarios[x])) < corr_max for x in dentro):
            elegidas.append(nombre)
    return elegidas
