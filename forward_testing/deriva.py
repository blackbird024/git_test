"""Detección de deriva en el forward test (PRE-REGISTRO §8). SOLO AVISA: no apaga el EA ni cambia la estrategia.

Bandas históricas: distribución de la media de N operaciones consecutivas (N = 50 zona de ruido, 15 RSI(2)) por
bootstrap de bloques de operaciones consecutivas (bloque de 10, 20.000 réplicas) sobre el histórico 2015-2026 (NOT OOS).
  - WARNING   si la media móvil de las últimas N operaciones forward < percentil 5 histórico.
  - ALERT     si < percentil 1.
  - OK        en otro caso; "muestra insuficiente" si hay menos de N operaciones.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
N_VENTANA = {"NOISE_ZONE": 50, "RSI2": 15}


def bandas(neto: np.ndarray, n: int, bloque: int = 10, replicas: int = 20000, semilla: int = 20260930) -> dict:
    x = np.asarray(neto, float)
    m = len(x)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(n / bloque))
    x2 = np.r_[x, x[:bloque]]
    ini = rng.integers(0, m, (replicas, k))
    idx = (ini[:, :, None] + np.arange(bloque)[None, None, :]).reshape(replicas, -1)[:, :n]
    medias = x2[idx].mean(axis=1)
    return {"n": n, "p1": float(np.percentile(medias, 1)), "p5": float(np.percentile(medias, 5)),
            "p50": float(np.percentile(medias, 50)), "p95": float(np.percentile(medias, 95)),
            "expectativa_historica": float(x.mean())}


def guardar_bandas(ops_por_estrategia: dict, ruta: Path = AQUI / "bandas_deriva.json") -> dict:
    b = {k: bandas(v.neto.to_numpy(), N_VENTANA[k]) for k, v in ops_por_estrategia.items()}
    ruta.write_text(json.dumps(b, indent=2), encoding="utf-8")
    return b


def evaluar(forward: pd.DataFrame, b: dict | None = None) -> pd.DataFrame:
    """forward: columnas strategy, net_pnl (en $ con 1 MNQ) en orden cronológico."""
    b = b or json.loads((AQUI / "bandas_deriva.json").read_text(encoding="utf-8"))
    filas = {}
    for est, banda in b.items():
        x = forward.loc[forward.strategy == est, "net_pnl"].astype(float).to_numpy()
        n = banda["n"]
        if len(x) < n:
            filas[est] = {"operaciones": len(x), "media_ultimas_n": np.nan, "estado": f"muestra insuficiente (< {n})"}
            continue
        m = x[-n:].mean()
        estado = "ALERT" if m < banda["p1"] else "WARNING" if m < banda["p5"] else "OK"
        filas[est] = {"operaciones": len(x), "media_ultimas_n": round(m, 2), "p5_historico": round(banda["p5"], 2),
                      "p1_historico": round(banda["p1"], 2), "estado": estado}
    return pd.DataFrame(filas).T


if __name__ == "__main__":
    f = pd.read_csv(AQUI / "survivors.csv")
    print(evaluar(f).to_string())
