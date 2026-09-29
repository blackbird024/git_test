"""Tamaño por riesgo y límites diarios. Nunca aumenta el riesgo tras una pérdida (sin martingala ni pyramiding)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Risk:
    sizing: str
    risk_pct: float
    fixed_contracts: int
    max_contracts: int
    point_value: float
    daily_loss_limit: float
    max_consecutive_losses: int
    max_trades_per_day: int
    _pnl: float = field(default=0.0, init=False)
    _n: int = field(default=0, init=False)
    _racha: int = field(default=0, init=False)
    _cap0: float = field(default=0.0, init=False)

    def new_day(self, equity: float) -> None:
        self._pnl, self._n, self._racha, self._cap0 = 0.0, 0, 0, equity

    def can_open(self) -> str:
        if self._n >= self.max_trades_per_day:
            return "max_trades_per_day"
        if self._pnl <= -self.daily_loss_limit / 100 * self._cap0:
            return "daily_loss_limit"
        if self.max_consecutive_losses and self._racha >= self.max_consecutive_losses:
            return "max_consecutive_losses"
        return ""

    def size(self, equity: float, stop_pts: float) -> int:
        """Contratos tales que contratos x stop x valor del punto <= riesgo permitido. 0 = no cabe ni uno."""
        if not (stop_pts > 0 and math.isfinite(stop_pts)):
            return 0
        if self.sizing == "fixed":
            return self.fixed_contracts
        n = math.floor(equity * self.risk_pct / 100 / (stop_pts * self.point_value) + 1e-9)
        return max(0, min(n, self.max_contracts))

    def opened(self) -> None:
        self._n += 1

    def closed(self, pnl: float) -> None:
        self._pnl += pnl
        self._racha = self._racha + 1 if pnl < 0 else 0
