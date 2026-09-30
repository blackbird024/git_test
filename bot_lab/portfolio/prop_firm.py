"""Modo prop firm (módulo aparte; NO se adapta la estrategia a las reglas).

Reglas simuladas sobre el P&L DIARIO (bootstrap por bloques de 20 sesiones):
  - límite de pérdida diaria: el día se corta en −límite (aproximación optimista: dentro del día el P&L podría haber
    pasado por −límite y recuperado, o la liquidación podría costar más);
  - drawdown trailing sobre el saldo de CIERRE diario (umbral = máximo saldo de cierre − trailing, deja de subir al
    llegar al saldo inicial);
  - objetivo de beneficio; máximo de contratos (escala entera del P&L por MNQ).
Con P&L diario no se puede simular el trailing intradía (con ganancias no realizadas): el riesgo real es MAYOR.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.validation.montecarlo import trayectorias


def simular(p: pd.Series, contratos: int, capital: float, limite_diario: float, trailing: float, objetivo: float,
            max_sesiones: int, bloque: int, n: int, semilla: int) -> dict:
    s = trayectorias(p * contratos, bloque, n, max_sesiones, semilla)
    s = np.maximum(s, -limite_diario)
    aprobadas = quemadas = 0
    dias_aprob = []
    for fila in s:
        saldo, pico = capital, capital
        res = None
        for d, x in enumerate(fila):
            saldo += x
            pico = max(pico, saldo)
            umbral = min(pico - trailing, capital)
            if saldo <= umbral:
                res = "quemada"
                break
            if saldo >= capital + objetivo:
                res = "aprobada"
                dias_aprob.append(d + 1)
                break
        if res == "aprobada":
            aprobadas += 1
        elif res == "quemada":
            quemadas += 1
    return {"contratos_por_estrategia": contratos, "prob_aprobar_%": round(aprobadas / n * 100, 1),
            "prob_quemar_%": round(quemadas / n * 100, 1),
            "prob_ni_una_ni_otra_%": round((n - aprobadas - quemadas) / n * 100, 1),
            "sesiones_medianas_hasta_aprobar": float(np.median(dias_aprob)) if dias_aprob else np.nan}
