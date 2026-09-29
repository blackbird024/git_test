"""Costes y reglas de llenado.

- Mercado (entradas y salidas por señal/tiempo/fin de sesión): apertura de la vela +/- (spread/2 + deslizamiento).
- Stop: nivel (o la apertura del minuto si abre más allá) +/- (spread/2 + deslizamiento).
- Target / parcial (límite): nivel exacto, solo si el precio lo supera en 1 tick; si el minuto abre más allá, apertura.
- Stop y target en el mismo minuto: se asume el stop (conservador).
- Comisión por contrato y lado. Bruto = sin comisión, spread ni deslizamiento.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    tick: float
    point_value: float
    commission_per_side: float
    slippage_ticks: float
    spread_ticks: float = 0.0

    @property
    def adverse(self) -> float:
        return (self.slippage_ticks + self.spread_ticks / 2) * self.tick

    def market(self, price: float, d: int, entry: bool) -> float:
        return price + d * self.adverse if entry else price - d * self.adverse

    def commission(self, qty: float) -> float:
        return 2 * self.commission_per_side * qty


def check_subbar(o, h, l, d, stop, target, tick):
    """Devuelve ('stop'|'target', precio_bruto) o None. Stop primero si ambos (conservador)."""
    if stop is not None and ((l <= stop) if d == 1 else (h >= stop)):
        return "stop", (min(o, stop) if d == 1 else max(o, stop))
    if target is not None and ((h >= target + tick) if d == 1 else (l <= target - tick)):
        return "target", (max(o, target) if d == 1 else min(o, target))
    return None
