"""Monte Carlo de evaluaciones Apex EOD.

Idea: generamos miles de "meses posibles" (caminos) y aplicamos a cada uno las mismas reglas
que src/risk/apex_eod.py, pero con numpy y para todos los caminos a la vez, para que sea rápido.

Dos formas de generar caminos:
  - bootstrap_days: remuestrea días reales de un backtest (con reemplazo). Sirve para ver la
    distribución de resultados posibles de una estrategia, no solo el camino histórico.
  - synthetic_days: días inventados con una ventaja (expectativa) conocida. Sirve para saber qué
    ventaja y qué riesgo por operación harían falta para aprobar.
"""
import numpy as np
import pandas as pd

from src.config import FirmAccount


def simulate_paths(pnl: np.ndarray, worst: np.ndarray, account: FirmAccount) -> pd.Series:
    """Aplica las reglas EOD a cada fila (un camino = una evaluación de N días de trading).

    pnl, worst: matrices (caminos x días) con el P&L del día y el peor momento intradía.
    Devuelve el % de caminos aprobados, suspendidos y caducados.
    """
    n, days = pnl.shape
    balance = np.full(n, account.start_balance, dtype=float)
    threshold = balance - account.max_drawdown
    goal = account.start_balance + account.profit_target
    status = np.zeros(n, dtype=int)  # 0 activa, 1 aprobada, -1 suspendida
    for d in range(days):
        active = status == 0
        w = np.maximum(worst[:, d], -account.daily_loss_limit)
        failed = active & (balance + w <= threshold)
        dll = worst[:, d] <= -account.daily_loss_limit
        if account.dll_fails_account:
            failed |= active & dll
        status[failed] = -1
        active &= ~failed
        day_pnl = np.where(dll, -account.daily_loss_limit, pnl[:, d])
        balance = np.where(active, balance + day_pnl, balance)
        passed = active & (balance >= goal)
        status[passed] = 1
        threshold = np.where(active, np.maximum(threshold, balance - account.max_drawdown), threshold)
        if account.threshold_cap is not None:
            threshold = np.minimum(threshold, account.threshold_cap)
    return pd.Series({
        "% aprobadas": (status == 1).mean() * 100,
        "% suspendidas": (status == -1).mean() * 100,
        "% caducadas": (status == 0).mean() * 100,
    }).round(1)


def bootstrap_days(daily: pd.DataFrame, n_paths: int, n_days: int, seed: int = 0):
    """Remuestrea días reales (pnl y peor momento van juntos, del mismo día)."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(daily), size=(n_paths, n_days))
    return daily.pnl.to_numpy()[idx], daily.min_intraday_pnl.to_numpy()[idx]


def synthetic_days(expectancy_r: float, risk: float, n_paths: int, n_days: int,
                   trades_per_day: int = 1, win_r: float = 1.5, seed: int = 0):
    """Días inventados: cada operación gana +win_r R o pierde -1R, con la probabilidad de acierto
    que da la expectativa pedida (ya neta de costes): E = p*win_r - (1-p)."""
    rng = np.random.default_rng(seed)
    p = (expectancy_r + 1) / (win_r + 1)
    wins = rng.random((n_paths, n_days, trades_per_day)) < p
    r = np.where(wins, win_r, -1.0) * risk
    pnl = r.sum(axis=2)
    # Peor momento: el mínimo del acumulado del día (operaciones una detrás de otra).
    worst = np.minimum(np.cumsum(r, axis=2).min(axis=2), 0.0)
    return pnl, worst
