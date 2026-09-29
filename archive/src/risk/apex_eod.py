"""Simulador de la evaluación EOD de Apex a partir del resumen diario del backtest.

Reglas que aplica (ver config/firms/apex_eod.yaml):
  - Umbral inicial = saldo inicial - drawdown máximo.
  - Durante el día el umbral está FIJO. Si el saldo, contando lo no realizado en el peor
    momento del día, toca o baja del umbral -> evaluación suspendida.
  - Límite de pérdida diaria (DLL): si la pérdida del día llega al DLL, Apex liquida.
    Según el supuesto configurado, eso solo para el día o también suspende la cuenta.
  - Al cierre: umbral = max(umbral, saldo_cierre - drawdown máximo), con un tope opcional.
  - Aprobada si el saldo de cierre llega al objetivo. Caduca a los `access_days` días naturales.

¿Por qué trabajar con el resumen diario y no operación a operación? Porque el motor
(src/engine/backtest.py) ya calcula el peor momento de cada día, y así podemos simular miles
de evaluaciones, empezando en cada fecha posible, en milisegundos.
"""
from dataclasses import dataclass

import pandas as pd

from src.config import FirmAccount

PASSED, FAILED, EXPIRED = "aprobada", "suspendida", "caducada"


@dataclass(frozen=True)
class EvaluationResult:
    start: pd.Timestamp
    outcome: str            # aprobada / suspendida / caducada
    end: pd.Timestamp
    trading_days: int
    final_balance: float
    reason: str             # detalle: "objetivo", "umbral_eod", "limite_diario", "tiempo"


def simulate_evaluation(daily: pd.DataFrame, account: FirmAccount, start) -> EvaluationResult:
    """Una evaluación empezando el día `start`. `daily` necesita las columnas pnl y min_intraday_pnl."""
    start = pd.Timestamp(start)
    deadline = start + pd.Timedelta(days=account.access_days)
    window = daily[(daily.index >= start) & (daily.index < deadline)]

    balance = account.start_balance
    threshold = balance - account.max_drawdown
    goal = account.start_balance + account.profit_target
    days = 0
    for date, row in window.iterrows():
        days += 1
        worst = row.min_intraday_pnl
        pnl = row.pnl
        dll_hit = worst <= -account.daily_loss_limit

        # 1) ¿Tocamos el umbral en el peor momento del día? (el DLL corta la caída antes)
        worst_balance = balance + max(worst, -account.daily_loss_limit)
        if worst_balance <= threshold:
            return EvaluationResult(start, FAILED, date, days, worst_balance, "umbral_eod")
        if dll_hit:
            if account.dll_fails_account:
                return EvaluationResult(start, FAILED, date, days,
                                        balance - account.daily_loss_limit, "limite_diario")
            pnl = -account.daily_loss_limit  # Apex liquida y el día termina con esa pérdida

        # 2) Cierre del día
        balance += pnl
        if balance >= goal:
            return EvaluationResult(start, PASSED, date, days, balance, "objetivo")
        threshold = max(threshold, balance - account.max_drawdown)
        if account.threshold_cap is not None:
            threshold = min(threshold, account.threshold_cap)

    end = window.index[-1] if len(window) else start
    return EvaluationResult(start, EXPIRED, end, days, balance, "tiempo")


def simulate_all_starts(daily: pd.DataFrame, account: FirmAccount) -> pd.DataFrame:
    """Una evaluación por cada fecha de inicio posible (solo fechas con 30 días completos por delante)."""
    last_valid = daily.index.max() - pd.Timedelta(days=account.access_days)
    starts = daily.index[daily.index <= last_valid]
    rows = [simulate_evaluation(daily, account, s).__dict__ for s in starts]
    return pd.DataFrame(rows)


def summarize(evals: pd.DataFrame) -> dict:
    """Porcentajes de aprobadas, suspendidas y caducadas."""
    if evals.empty:
        return {"evaluaciones": 0}
    pct = evals.outcome.value_counts(normalize=True) * 100
    passed = evals[evals.outcome == PASSED]
    return {
        "evaluaciones": len(evals),
        "% aprobadas": round(pct.get(PASSED, 0.0), 1),
        "% suspendidas": round(pct.get(FAILED, 0.0), 1),
        "% caducadas": round(pct.get(EXPIRED, 0.0), 1),
        "dias medios hasta aprobar": round(passed.trading_days.mean(), 1) if len(passed) else None,
    }
