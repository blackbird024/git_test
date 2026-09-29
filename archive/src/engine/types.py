"""Tipos de datos básicos del motor: señales, posiciones y operaciones cerradas."""
from dataclasses import dataclass

import pandas as pd

LONG = 1
SHORT = -1


@dataclass(frozen=True)
class Signal:
    """Lo que una estrategia 'pide'. El motor y el gestor de riesgo deciden si se ejecuta.

    `time` es la marca de tiempo de la vela en cuyo CIERRE se conoce la señal.
    La entrada nunca se hace en esa vela: se hace en la apertura de una vela posterior,
    igual que en la vida real, donde tú necesitas unos segundos para poner la orden.
    """
    strategy: str
    instrument: str
    direction: int          # LONG (+1) o SHORT (-1)
    time: pd.Timestamp
    stop: float             # precio del stop loss (obligatorio)
    target: float           # precio del take profit (obligatorio)


@dataclass
class Position:
    signal: Signal
    qty: int
    entry_time: pd.Timestamp
    entry_price: float
    risk_usd: float         # pérdida si salta el stop (con costes)


@dataclass(frozen=True)
class Trade:
    strategy: str
    instrument: str
    direction: int
    qty: int
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str        # "stop", "target" o "cierre_forzado"
    pnl_gross: float
    costs: float
    pnl_net: float
    risk_usd: float

    @property
    def r_multiple(self) -> float:
        """Resultado medido en 'R' (1R = lo que se arriesgaba). +2R = ganó el doble de lo arriesgado."""
        return self.pnl_net / self.risk_usd if self.risk_usd else 0.0
