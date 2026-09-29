"""Métricas de una lista de operaciones (columnas: neto en $, r en múltiplos de R, t_entrada en UTC).

- acierto: % de operaciones con beneficio neto > 0
- profit factor: ganancias brutas / pérdidas brutas (> 1 gana dinero)
- R medio: resultado medio por operación en unidades de riesgo
- t: estadístico t del R medio (|t| > 2 ≈ difícil de explicar solo por azar)
- drawdown máximo: mayor caída desde un máximo del saldo acumulado
- racha perdedora: mayor número de operaciones perdedoras seguidas
"""
import numpy as np
import pandas as pd


def racha(mascara) -> int:
    mejor = actual = 0
    for v in mascara:
        actual = actual + 1 if v else 0
        mejor = max(mejor, actual)
    return mejor


def resumen(ops: pd.DataFrame) -> dict:
    if ops.empty:
        return {"operaciones": 0}
    neto, r = ops.neto, ops.r
    ganado, perdido = neto[neto > 0].sum(), -neto[neto < 0].sum()
    saldo = neto.cumsum()
    return {
        "operaciones": len(ops),
        "acierto_%": round((neto > 0).mean() * 100, 1),
        "profit_factor": round(ganado / perdido, 2) if perdido > 0 else float("inf"),
        "R_medio": round(r.mean(), 3),
        "t": round(r.mean() / r.std() * np.sqrt(len(r)), 2) if len(r) > 1 and r.std() > 0 else float("nan"),
        "neto_$": round(neto.sum(), 0),
        "drawdown_max_$": round((saldo - saldo.cummax()).min(), 0),
        "racha_perdedora": racha(neto <= 0),
    }


def por_anio(ops: pd.DataFrame) -> pd.DataFrame:
    if ops.empty:
        return pd.DataFrame()
    anio = pd.DatetimeIndex(ops.t_entrada).year
    return pd.DataFrame({a: resumen(g) for a, g in ops.groupby(anio)}).T.drop(columns=["drawdown_max_$"])
