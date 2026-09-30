"""Bootstrap por bloques de sesiones y Monte Carlo del P&L diario (CRITERIOS.md §6).

- IC 95 % de la expectativa por operación: auditoria/src/metricas.ic_bloques (bloques circulares de 20 sesiones).
- Distribuciones a 1 año (252 sesiones): remuestreo por bloques del P&L diario (conserva la autocorrelación de corto
  plazo). P&L del año, drawdown máximo, P(año negativo), P(drawdown ≥ umbrales) y P(ruina = perder el 50 % del capital).
Supuesto: el pasado es representativo del futuro. No es una predicción.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trayectorias(p: pd.Series, bloque: int, n: int, horizonte: int, semilla: int) -> np.ndarray:
    x = p.to_numpy(float)
    m = len(x)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(horizonte / bloque))
    x2 = np.r_[x, x[:bloque]]
    ini = rng.integers(0, m, (n, k))
    idx = (ini[:, :, None] + np.arange(bloque)[None, None, :]).reshape(n, -1)[:, :horizonte]
    return x2[idx]


def distribucion(p: pd.Series, capital: float, bloque: int, n: int, horizonte: int, semilla: int,
                 umbrales=(2500, 5000)) -> dict:
    s = trayectorias(p, bloque, n, horizonte, semilla)
    eq = np.cumsum(s, axis=1)
    pico = np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), eq], axis=1), axis=1)[:, 1:]
    dd = (eq - pico).min(axis=1)
    fin = eq[:, -1]
    out = {"P&L_año_p5_$": round(np.percentile(fin, 5), 0), "P&L_año_p50_$": round(np.percentile(fin, 50), 0),
           "P&L_año_p95_$": round(np.percentile(fin, 95), 0), "prob_año_negativo_%": round((fin < 0).mean() * 100, 1),
           "max_dd_p50_$": round(np.percentile(dd, 50), 0), "max_dd_p95_$": round(np.percentile(dd, 5), 0),
           "max_dd_p99_$": round(np.percentile(dd, 1), 0)}
    for u in umbrales:
        out[f"prob_dd_≥{u}_%"] = round((dd <= -u).mean() * 100, 1)
    out["prob_ruina_50%_capital_%"] = round((eq.min(axis=1) <= -0.5 * capital).mean() * 100, 2)
    return out
