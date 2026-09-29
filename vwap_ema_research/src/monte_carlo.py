"""Monte Carlo sobre la secuencia de operaciones (solo análisis de robustez; no modifica la estrategia).

Dos métodos: (1) barajar el orden (mismo resultado final, distinta trayectoria: distribución de drawdown y rachas);
(2) remuestreo con reemplazo (distribución del resultado). Limitación: supone operaciones independientes; las
rachas de régimen reales pueden producir drawdowns peores.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import racha


def monte_carlo(net: np.ndarray, capital: float, n: int, seed: int, umbrales_pct: list) -> dict:
    net = np.asarray(net, float)
    if len(net) < 10:
        return {"nota": "menos de 10 operaciones: no se hace Monte Carlo"}
    rng = np.random.default_rng(seed)
    dd_pct, rachas, finales = np.empty(n), np.empty(n), np.empty(n)
    for i in range(n):
        orden = rng.permutation(net)
        eq = capital + np.cumsum(orden)
        pk = np.maximum.accumulate(np.r_[capital, eq])[1:]
        dd_pct[i] = ((eq - pk) / pk).min() * 100
        rachas[i] = racha(orden < 0)
        finales[i] = rng.choice(net, len(net), replace=True).sum()
    pct = lambda a, q: float(np.round(np.percentile(a, q), 2))  # noqa: E731
    out = {"n_sim": n, "trades": len(net),
           "retorno_usd_p5": pct(finales, 5), "retorno_usd_p50": pct(finales, 50), "retorno_usd_p95": pct(finales, 95),
           "prob_retorno_negativo_%": float(round((finales < 0).mean() * 100, 1)),
           "max_dd_%_p50": pct(dd_pct, 50), "max_dd_%_p95_peor": pct(dd_pct, 5),
           "racha_perdedora_p50": pct(rachas, 50), "racha_perdedora_p95": pct(rachas, 95)}
    for u in umbrales_pct:
        out[f"prob_dd_mayor_{u}%"] = float(round((dd_pct < -u).mean() * 100, 1))
    return out


def as_frame(res: dict) -> pd.DataFrame:
    return pd.DataFrame([res])
