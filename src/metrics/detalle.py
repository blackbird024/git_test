"""Métricas detalladas para una lista de operaciones (columnas: neto en $, r en R, direccion, t_entrada en UTC).
Complementa a src/metrics/metricas.py sin cambiarlo."""
import numpy as np
import pandas as pd

from src.metrics.metricas import racha

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def completas(ops: pd.DataFrame) -> dict:
    if ops.empty:
        return {"operaciones": 0}
    neto, r = ops.neto, ops.r
    gan, per = neto[neto > 0], neto[neto <= 0]
    saldo, saldo_r = neto.cumsum(), r.cumsum()
    pf = gan.sum() / -per.sum() if per.sum() < 0 else float("inf")
    return {
        "operaciones": len(ops),
        "acierto_%": round((neto > 0).mean() * 100, 1),
        "ganancia_media_$": round(gan.mean(), 2) if len(gan) else 0.0,
        "perdida_media_$": round(per.mean(), 2) if len(per) else 0.0,
        "expectativa_$": round(neto.mean(), 2),
        "profit_factor": round(pf, 2),
        "neto_$": round(neto.sum(), 0),
        "R_medio": round(r.mean(), 3),
        "R_mediano": round(r.median(), 3),
        "t": round(r.mean() / r.std() * np.sqrt(len(r)), 2) if len(r) > 1 else float("nan"),
        "drawdown_max_$": round((saldo - saldo.cummax().clip(lower=0)).min(), 0),
        "drawdown_max_R": round((saldo_r - saldo_r.cummax().clip(lower=0)).min(), 2),
        "racha_perdedora_max": racha(neto <= 0),
        "racha_ganadora_max": racha(neto > 0),
    }


def _agrupar(ops: pd.DataFrame, clave, orden=None) -> pd.DataFrame:
    filas = {}
    for k, g in ops.groupby(clave):
        m = completas(g)
        filas[k] = {c: m[c] for c in ("operaciones", "acierto_%", "profit_factor", "R_medio", "neto_$")}
    t = pd.DataFrame(filas).T
    return t.reindex([o for o in orden if o in t.index]) if orden else t


def desgloses(ops: pd.DataFrame, zona: str = "Europe/London") -> dict:
    local = pd.DatetimeIndex(ops.t_entrada).tz_convert(zona)
    return {
        "por_anio": _agrupar(ops, local.year),
        "por_mes": _agrupar(ops, [MESES[m - 1] for m in local.month], MESES),
        "largos_vs_cortos": _agrupar(ops, ops.direccion.map({1: "LARGO", -1: "CORTO"}).to_numpy(), ["LARGO", "CORTO"]),
        "por_dia_semana": _agrupar(ops, [DIAS[d] for d in local.weekday], DIAS),
    }
