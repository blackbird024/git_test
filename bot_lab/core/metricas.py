"""Métricas completas del laboratorio. Reutiliza auditoria/src/metricas.py (P&L diario por sesión, IC por bloques).

Entrada: operaciones con `neto`, `bruto`, `r`, `t_entrada`, `t_salida` (UTC) y, si existen, `mae_pts`, `mfe_pts`,
`riesgo_pts`. P&L diario = día NY de SALIDA, con 0 en las sesiones sin operaciones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from auditoria.src import metricas as mt


def _dd_episodios(eq: np.ndarray) -> tuple[float, float]:
    """(drawdown máximo, drawdown medio de los episodios) sobre una curva de P&L acumulado que empieza en 0."""
    pico = np.maximum.accumulate(np.r_[0.0, eq])[1:]
    dd = eq - pico
    if len(dd) == 0:
        return 0.0, 0.0
    episodios, actual = [], 0.0
    for v in dd:
        if v < 0:
            actual = min(actual, v)
        elif actual < 0:
            episodios.append(actual)
            actual = 0.0
    if actual < 0:
        episodios.append(actual)
    return float(dd.min()), float(np.mean(episodios)) if episodios else 0.0


def _momento(x: np.ndarray, k: int) -> float:
    if len(x) < 4 or x.std() == 0:
        return np.nan
    z = (x - x.mean()) / x.std()
    return float(np.mean(z ** k) - (3 if k == 4 else 0))


def completas(ops: pd.DataFrame, sesiones: pd.DatetimeIndex, capital: float = 25000) -> dict:
    n = len(ops)
    if n == 0:
        return {"operaciones": 0}
    x = ops.neto.to_numpy(float)
    gan, per = x[x > 0], x[x < 0]
    d = mt.diario(ops, sesiones)
    pnl = d.pnl.to_numpy(float)
    eq = np.cumsum(pnl)
    dd_max, dd_medio = _dd_episodios(eq)
    anios = max(len(d) / 252, 1e-9)
    ret = pnl / capital
    sd = ret.std(ddof=1) if len(ret) > 1 else 0
    abajo = np.sqrt(np.mean(np.minimum(ret, 0) ** 2))
    idx = pd.DatetimeIndex(d.index)
    semana = pd.Series(pnl, idx).resample("W").sum()
    mes = pd.Series(pnl, idx).resample("ME").sum()
    anio = pd.Series(pnl, idx).groupby(idx.year).sum()
    dur = (pd.to_datetime(ops.t_salida) - pd.to_datetime(ops.t_entrada)).dt.total_seconds() / 60
    neto_anual = x.sum() / anios
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    out = {
        "operaciones": n, "operaciones_por_año": round(n / anios, 1),
        "acierto_%": round((x > 0).mean() * 100, 1),
        "ganancia_media_$": round(gan.mean(), 2) if len(gan) else 0.0,
        "perdida_media_$": round(per.mean(), 2) if len(per) else 0.0,
        "payoff": round(gan.mean() / -per.mean(), 2) if len(gan) and len(per) else np.nan,
        "ganancia_bruta_$": round(gan.sum(), 0), "perdida_bruta_$": round(per.sum(), 0),
        "neto_$": round(x.sum(), 0), "costes_$": round((ops.bruto - ops.neto).sum(), 0) if "bruto" in ops else np.nan,
        "profit_factor": round(gan.sum() / -per.sum(), 3) if len(per) else np.inf,
        "expectativa_$": round(x.mean(), 2),
        "t": round(x.mean() / se, 2) if se and se > 0 else np.nan,
        "IC95_iid_$": mt.ic_iid(pd.Series(x)),
        "max_dd_$": round(dd_max, 0), "dd_medio_$": round(dd_medio, 0),
        "sharpe": round(ret.mean() / sd * np.sqrt(252), 2) if sd > 0 else np.nan,
        "sortino": round(ret.mean() / abajo * np.sqrt(252), 2) if abajo > 0 else np.nan,
        "calmar": round(neto_anual / -dd_max, 2) if dd_max < 0 else np.inf,
        "neto_anual_$": round(neto_anual, 0),
        "racha_perdedora": mt.racha(x < 0), "racha_ganadora": mt.racha(x > 0),
        "duracion_media_min": round(dur.mean(), 1), "duracion_mediana_min": round(dur.median(), 1),
        "mediana_$": round(float(np.median(x)), 2),
        "p5_$": round(float(np.percentile(x, 5)), 1), "p25_$": round(float(np.percentile(x, 25)), 1),
        "p75_$": round(float(np.percentile(x, 75)), 1), "p95_$": round(float(np.percentile(x, 95)), 1),
        "asimetria": round(_momento(x, 3), 2), "curtosis_exceso": round(_momento(x, 4), 2),
        "peor_operacion_$": round(x.min(), 0), "mejor_operacion_$": round(x.max(), 0),
        "peor_dia_$": round(pnl.min(), 0), "peor_semana_$": round(semana.min(), 0),
        "peor_mes_$": round(mes.min(), 0), "peor_año_$": round(anio.min(), 0),
        "mes_medio_$": round(mes.mean(), 0), "meses_positivos_%": round((mes > 0).mean() * 100, 1),
        "años_positivos": f"{int((anio > 0).sum())}/{len(anio)}",
        "frac_años_positivos": round(float((anio > 0).mean()), 2),
        "anual_$": {int(k): round(v, 0) for k, v in anio.items()},
    }
    if "r" in ops and ops.r.notna().any():
        r = ops.r.dropna()
        out["expectativa_R"] = round(r.mean(), 4)
    if "mae_pts" in ops and "riesgo_pts" in ops:
        rp = ops.riesgo_pts.replace(0, np.nan)
        out["MAE_medio_R"] = round((ops.mae_pts / rp).mean(), 3)
        out["MFE_medio_R"] = round((ops.mfe_pts / rp).mean(), 3)
        out["MAE_medio_pts"] = round(ops.mae_pts.mean(), 2)
        out["MFE_medio_pts"] = round(ops.mfe_pts.mean(), 2)
    return out


def rapidas(ops: pd.DataFrame) -> dict:
    """Métricas básicas para cribar muchas variantes (sin P&L diario)."""
    n = len(ops)
    if n == 0:
        return {"operaciones": 0, "expectativa_$": np.nan, "t": np.nan, "profit_factor": np.nan, "neto_$": 0.0}
    x = ops.neto.to_numpy(float)
    per = -x[x < 0].sum()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return {"operaciones": n, "expectativa_$": round(x.mean(), 2),
            "t": round(x.mean() / se, 2) if se and se > 0 else np.nan,
            "profit_factor": round(x[x > 0].sum() / per, 3) if per > 0 else np.inf,
            "neto_$": round(x.sum(), 0), "acierto_%": round((x > 0).mean() * 100, 1)}


def ic_bloques(ops: pd.DataFrame, sesiones: pd.DatetimeIndex, bloque: int, n: int, semilla: int):
    return mt.ic_bloques(mt.diario(ops, sesiones), bloque, n, semilla)


def diario(ops: pd.DataFrame, sesiones: pd.DatetimeIndex) -> pd.Series:
    if len(ops) == 0:
        return pd.Series(0.0, index=pd.DatetimeIndex(sesiones).normalize())
    return mt.diario(ops, sesiones).pnl
