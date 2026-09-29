"""Simulador del drawdown TRAILING INTRADÍA de Apex.

Regla: umbral = saldo máximo alcanzado (incluidas ganancias NO realizadas) - drawdown.
Si en algún momento el saldo (incluido lo no realizado) toca el umbral, la cuenta se quema.
Opcionalmente el umbral deja de subir al llegar a saldo_inicial + `stop_trailing_at`.

Cada operación llega como un "recorrido": la lista de su P&L en dólares punto a punto
(ver src/strategies/orb_5m.py). Así la simulación es exacta con la información disponible.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrailingAccount:
    start_balance: float = 50_000
    drawdown: float = 2_000
    stop_trailing_at: float | None = None   # dólares sobre el saldo inicial; None = nunca para

    def threshold(self, peak: float) -> float:
        t = peak - self.drawdown
        if self.stop_trailing_at is not None:
            t = min(t, self.start_balance + self.stop_trailing_at)
        return t


def run_sequence(paths: list, account: TrailingAccount, restart: bool = True) -> list[dict]:
    """Recorre las operaciones en orden. Devuelve una fila por cuenta quemada
    (índice de la operación, saldo máximo, saldo al quemarse). Si `restart`, tras quemarse se
    abre otra cuenta nueva y se sigue, para contar cuántas se habrían quemado en todo el periodo."""
    burns = []
    balance = peak = account.start_balance
    for i, path in enumerate(paths):
        for x in path:
            eq = balance + x
            peak = max(peak, eq)
            if eq <= account.threshold(peak):
                burns.append({"trade_idx": i, "peak": peak, "equity": eq})
                break
        else:
            balance += path[-1]
            continue
        if not restart:
            return burns
        balance = peak = account.start_balance
    return burns


def path_summary(paths: list) -> pd.DataFrame:
    """Resume cada recorrido en 4 números suficientes para el Monte Carlo (sin tope de trailing):
      final   = resultado de la operación
      mfe     = mejor momento (sube el saldo máximo)
      mae     = peor momento
      max_dd  = mayor caída desde un máximo DENTRO de la operación
    Con saldo E y máximo previo P, la cuenta se quema en la operación si
      mae <= P - E - drawdown   o   max_dd >= drawdown."""
    rows = []
    for p in paths:
        a = np.asarray(p, dtype=float)
        run_max = np.maximum.accumulate(a)
        rows.append({"final": a[-1], "mfe": a.max(), "mae": a.min(), "max_dd": (run_max - a).max()})
    return pd.DataFrame(rows)


def monte_carlo(summary: pd.DataFrame, account: TrailingAccount, n_sims: int, seed: int = 0) -> dict:
    """Reordena las operaciones al azar `n_sims` veces y mide:
      - probabilidad de tocar el drawdown trailing en algún momento;
      - drawdown máximo (saldo cerrado) típico y malo (percentiles 50 y 95)."""
    if account.stop_trailing_at is not None:
        raise NotImplementedError("El Monte Carlo rápido asume trailing sin tope (stop_trailing_at=None).")
    rng = np.random.default_rng(seed)
    final, mfe, mae, mdd = (summary[c].to_numpy() for c in ("final", "mfe", "mae", "max_dd"))
    n = len(final)
    E = np.zeros(n_sims)            # saldo relativo al inicial
    P = np.zeros(n_sims)            # máximo relativo al inicial
    closed_peak = np.zeros(n_sims)
    max_closed_dd = np.zeros(n_sims)
    burned = np.zeros(n_sims, dtype=bool)
    burn_at = np.full(n_sims, -1)
    D = account.drawdown
    perms = np.argsort(rng.random((n_sims, n)), axis=1)   # una permutación distinta por simulación
    for k in range(n):
        j = perms[:, k]
        hit = (~burned) & ((mae[j] <= P - E - D) | (mdd[j] >= D))
        burn_at[hit] = k
        burned |= hit
        P = np.maximum(P, E + mfe[j])
        E = E + final[j]
        closed_peak = np.maximum(closed_peak, E)
        max_closed_dd = np.maximum(max_closed_dd, closed_peak - E)
    return {
        "prob_quemar_%": round(burned.mean() * 100, 1),
        "operacion_mediana_al_quemar": int(np.median(burn_at[burned])) if burned.any() else None,
        "dd_cerrado_p50": round(np.percentile(max_closed_dd, 50), 0),
        "dd_cerrado_p95": round(np.percentile(max_closed_dd, 95), 0),
    }
