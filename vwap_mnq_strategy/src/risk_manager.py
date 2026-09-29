"""Tamaño de posición y límites de riesgo por sesión."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class RiskManager:
    sizing: str                 # "risk_pct" | "fixed"
    risk_pct: float             # % del capital actual
    fixed_contracts: int
    max_contracts: int
    min_contracts: int
    point_value: float
    daily_loss_limit_pct: float
    max_trades_per_session: int
    pause_after_losses: int
    # estado de la sesión
    _pnl_dia: float = field(default=0.0, init=False)
    _ops_dia: int = field(default=0, init=False)
    _perdidas_seguidas: int = field(default=0, init=False)
    _capital_inicio_dia: float = field(default=0.0, init=False)

    def new_session(self, equity: float) -> None:
        self._pnl_dia, self._ops_dia, self._perdidas_seguidas = 0.0, 0, 0
        self._capital_inicio_dia = equity

    def can_open(self) -> tuple[bool, str]:
        if self._ops_dia >= self.max_trades_per_session:
            return False, "max_operaciones_sesion"
        if self._pnl_dia <= -self.daily_loss_limit_pct / 100 * self._capital_inicio_dia:
            return False, "limite_perdida_diaria"
        if self.pause_after_losses and self._perdidas_seguidas >= self.pause_after_losses:
            return False, "pausa_por_perdidas"
        return True, ""

    def size(self, equity: float, stop_distance_pts: float) -> int:
        """Contratos. 0 si el tamaño calculado es menor que el mínimo (no se opera)."""
        if not (stop_distance_pts > 0) or not math.isfinite(stop_distance_pts):
            return 0
        if self.sizing == "fixed":
            return self.fixed_contracts
        riesgo = equity * self.risk_pct / 100
        n = math.floor(riesgo / (stop_distance_pts * self.point_value) + 1e-9)
        n = min(n, self.max_contracts)
        return n if n >= self.min_contracts else 0

    def on_open(self) -> None:
        self._ops_dia += 1

    def on_close(self, pnl: float) -> None:
        self._pnl_dia += pnl
        self._perdidas_seguidas = self._perdidas_seguidas + 1 if pnl < 0 else 0
