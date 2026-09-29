"""Monte Carlo: se baraja el orden de las operaciones muchas veces y se mide el drawdown máximo de cada orden.
Responde a: "con estas mismas operaciones, ¿qué caída podría haber sufrido si hubieran llegado en otro orden?"."""
import numpy as np
import pandas as pd


def drawdowns(neto: pd.Series, simulaciones: int = 1000, semilla: int = 42) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    x = neto.to_numpy(dtype=float)
    dd = np.empty(simulaciones)
    for k in range(simulaciones):
        saldo = np.cumsum(rng.permutation(x))
        dd[k] = (saldo - np.maximum.accumulate(np.maximum(saldo, 0))).min()
    return dd


def resumen_mc(neto: pd.Series, simulaciones: int = 1000, semilla: int = 42) -> dict:
    dd = drawdowns(neto, simulaciones, semilla)
    return {"simulaciones": simulaciones, "dd_mediano_$": round(float(np.percentile(dd, 50)), 0),
            "dd_p95_$": round(float(np.percentile(dd, 5)), 0), "dd_peor_$": round(float(dd.min()), 0)}
