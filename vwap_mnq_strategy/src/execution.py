"""Modelo de ejecución y costes.

- Órdenes a mercado (entradas, salidas por señal, por tiempo y fin de sesión): precio de apertura de la vela
  +/- deslizamiento en ticks en contra.
- Stop: se activa si una sub-vela toca el nivel. Precio = nivel - deslizamiento; si la sub-vela ABRE más allá del
  stop (hueco), se ejecuta en esa apertura - deslizamiento.
- Target (orden límite): sin deslizamiento. Con `target_requires_through`, solo se llena si el precio supera el
  nivel en al menos 1 tick (tocarlo no garantiza el llenado). Si abre más allá, se llena en la apertura.
- Stop y target en la MISMA sub-vela: se asume el stop (hipótesis conservadora; el orden real se desconoce).
- Comisión por contrato y lado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    tick: float
    point_value: float
    commission_per_side: float
    slippage_ticks: float
    target_requires_through: bool = True

    def market(self, price: float, direction: int, is_entry: bool) -> float:
        """Precio de ejecución a mercado. direction = sentido de la POSICIÓN (+1 largo, -1 corto)."""
        s = self.slippage_ticks * self.tick
        return price + direction * s if is_entry else price - direction * s

    def commission(self, qty: int) -> float:
        return 2 * self.commission_per_side * qty


def check_exit_subbar(o: float, h: float, l: float, direction: int, stop: float | None, target: float | None,
                      cm: CostModel) -> tuple[str, float, float] | None:
    """Comprueba una sub-vela. Devuelve (motivo, precio_bruto, precio_ejecutado) o None.
    precio_bruto = nivel teórico sin deslizamiento (para el resultado bruto)."""
    d, tick = direction, cm.tick
    toca_stop = stop is not None and ((l <= stop) if d == 1 else (h >= stop))
    if target is not None:
        umbral = target + d * tick if cm.target_requires_through else target
        toca_target = (h >= umbral) if d == 1 else (l <= umbral)
    else:
        toca_target = False
    if toca_stop:                                            # también si toca el target: conservador
        bruto = min(o, stop) if d == 1 else max(o, stop)     # hueco: se ejecuta en la apertura
        return "stop", bruto, cm.market(bruto, d, is_entry=False)
    if toca_target:
        bruto = max(o, target) if d == 1 else min(o, target)
        return "target", bruto, bruto
    return None
