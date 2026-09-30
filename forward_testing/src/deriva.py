"""Monitor de deriva (SOLO INFORMATIVO: no apaga, no cambia parámetros, no cambia el riesgo, no crea filtros).

Ventanas móviles: zona de ruido 20/50/100 operaciones; RSI(2) 10/15/25.
Bandas históricas: distribución de la media de N operaciones consecutivas por bootstrap de bloques de operaciones
consecutivas (bloque 10, 20.000 réplicas, semilla 20260930) sobre las operaciones de referencia 2015-2026 (NOT OOS).
Umbral OFICIAL (Survivor Analysis v1.0): zona de ruido, media de las últimas 50 < −20,5 $; RSI(2), media de las
últimas 15 < −71 $. Estados por ventana: OK / WARNING (< p5) / ALERT (< p1) / muestra insuficiente.

ESCALA: el NQ vale hoy 6-7 veces más que en 2015, así que el P&L en $ por operación es hoy mucho más disperso que la
media histórica. Por eso cada ventana se evalúa DOS veces: en $ (umbrales oficiales, como se pidió) y en % del precio de
entrada (bandas comparables entre épocas). Si solo salta la alarma en $, lo más probable es el efecto de escala.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEMILLA = 20260930


def bandas(neto: np.ndarray, n: int, bloque: int = 10, replicas: int = 20000, semilla: int = SEMILLA) -> dict:
    x = np.asarray(neto, float)
    m = len(x)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(n / bloque))
    x2 = np.r_[x, x[:bloque]]
    ini = rng.integers(0, m, (replicas, k))
    idx = (ini[:, :, None] + np.arange(bloque)[None, None, :]).reshape(replicas, -1)[:, :n]
    med = x2[idx].mean(axis=1)
    return {"n": n, "p1": round(float(np.percentile(med, 1)), 4), "p5": round(float(np.percentile(med, 5)), 4),
            "p50": round(float(np.percentile(med, 50)), 4), "p95": round(float(np.percentile(med, 95)), 4),
            "p99": round(float(np.percentile(med, 99)), 4)}


def pct_referencia(ref: pd.DataFrame, estrategia: str) -> np.ndarray:
    """P&L neto de la referencia en % del precio de entrada (1 MNQ = 2 $/punto)."""
    if estrategia == "RSI2" and "ret_%" in ref:
        return ref["ret_%"].to_numpy(float)
    return (ref.neto / (ref.entrada * 2.0) * 100).to_numpy(float)


def todas_las_bandas(referencia: dict, ventanas: dict, pct: bool = False) -> dict:
    return {est: {str(n): bandas(pct_referencia(referencia[est], est) if pct else referencia[est].neto.to_numpy(), n)
                  for n in ventanas[est]} for est in ventanas}


def evaluar(forward: dict, b: dict, oficial: dict, col: str = "neto_$") -> pd.DataFrame:
    """forward: {estrategia: DataFrame de operaciones CERRADAS en orden, con neto_$}. Una fila por estrategia y ventana."""
    filas = []
    for est, vent in b.items():
        x = forward.get(est, pd.DataFrame()).get(col, pd.Series(dtype=float)).astype(float).to_numpy()
        for n_txt, banda in vent.items():
            n = int(n_txt)
            fila = {"estrategia": est, "medida": col, "ventana": n, "operaciones": len(x), "p1_hist": banda["p1"], "p5_hist": banda["p5"],
                    "p50_hist": banda["p50"], "p95_hist": banda["p95"]}
            if len(x) < n:
                fila.update(media_ultimas=np.nan, estado=f"muestra insuficiente ({len(x)}/{n})", umbral_oficial=np.nan)
            else:
                m = x[-n:].mean()
                estado = "ALERT" if m < banda["p1"] else "WARNING" if m < banda["p5"] else "OK"
                fila.update(media_ultimas=round(m, 2), estado=estado)
            of = oficial.get(est, {}) if col == "neto_$" else {}
            if of.get("ventana") == n:
                fila["umbral_oficial"] = of["media_$"]
                if len(x) >= n and x[-n:].mean() < of["media_$"]:
                    fila["estado"] = "ALERTA OFICIAL (informativa)"
            filas.append(fila)
    return pd.DataFrame(filas)


def serie_movil(neto: pd.Series, n: int) -> pd.Series:
    return neto.astype(float).rolling(n).mean()
