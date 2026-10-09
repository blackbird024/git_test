"""Motor de reglas de la cuenta Topstep 50K Combine (parámetros en config/CONFIG_RIESGO.yaml).

Entrada: operaciones de 1 contrato con su peor excursión adversa intradía (MAE). Para N contratos se escala.
Simula un intento de Combine desde un día de inicio dado, día a día y operación a operación:
- Límite personal diario: tras alcanzar la pérdida del día `stop_diario_usd`, no se abren más operaciones.
- Daily Loss Limit: si el P&L del día (con el flotante) llega a −DLL, la operación se cierra en ese nivel y el día acaba.
- MLL: si saldo + flotante toca el umbral, el intento fracasa. El umbral sube con el máximo saldo de CIERRE.
- Aprobado: beneficio ≥ objetivo y mejor día ≤ pct × beneficio total.
Limitación: el flotante se aproxima con la MAE de cada operación (el peor punto); no se modela el orden exacto
entre la MAE de una operación y el cierre de otra del mismo día.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

CFG = Path(__file__).resolve().parents[1] / "config" / "CONFIG_RIESGO.yaml"


@dataclass
class Rules:
    start: float
    target: float
    mll: float
    mll_lock: float
    dll: float
    consistency: float
    personal_daily_stop: float

    @classmethod
    def load(cls):
        c = yaml.safe_load(CFG.read_text())
        t, p = c["topstep_50k_combine"], c["limites_personales"]
        return cls(t["saldo_inicial"], t["objetivo_beneficio"]["valor"], t["max_loss_limit"]["valor"],
                   t["max_loss_limit"]["deja_de_subir_en"], t["daily_loss_limit"]["valor"],
                   t["consistencia"]["max_mejor_dia_pct"], p["stop_diario_usd"])


def attempt(days, R: Rules, max_days=250):
    """`days`: lista de listas de (pnl_usd, mae_usd ≤ 0) por operación, ya escaladas al tamaño.
    Devuelve (resultado, días_operados) con resultado en {"aprobado", "suspendido", "sin_resolver"}."""
    bal = R.start
    peak_close = R.start
    best_day = 0.0
    for n, trades in enumerate(days[:max_days], start=1):
        thr = min(peak_close - R.mll, R.mll_lock)
        day = 0.0
        for pnl, mae in trades:
            if day <= -R.personal_daily_stop:
                break
            worst = day + mae
            if bal + worst <= thr:
                return "suspendido", n
            if worst <= -R.dll:
                day = -R.dll
                break
            day += pnl
            if bal + day <= thr:
                return "suspendido", n
        bal += day
        peak_close = max(peak_close, bal)
        best_day = max(best_day, day)
        profit = bal - R.start
        if profit >= R.target and best_day <= R.consistency * profit:
            return "aprobado", n
    return "sin_resolver", min(len(days), max_days)
