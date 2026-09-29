"""Costes: comisión por contrato y lado, y deslizamiento en ticks según la hora.

Deslizamiento: 1 tick por lado en general y 2 ticks en las aperturas de sesión, porque en esos minutos
los precios se mueven rápido y la orden se llena peor. Las aperturas se definen en la zona horaria de cada
mercado, así que son correctas también en las semanas en que el horario de verano de EE. UU. y de Europa
no coincide:
  - Londres:              07:50-08:10 hora de Londres  (08:50-09:10 en Italia)
  - Nueva York (contado): 09:25-09:45 hora de Nueva York (15:25-15:45 en Italia casi todo el año)
  - Reapertura de Globex: 18:00-18:15 hora de Nueva York (00:00-00:15 en Italia casi todo el año)
Las órdenes límite (objetivo) no tienen deslizamiento.
"""
from dataclasses import dataclass

import pandas as pd

from src.horas import LONDRES, NUEVA_YORK, en_ventana

APERTURAS = ((LONDRES, "07:50", "08:10"), (NUEVA_YORK, "09:25", "09:45"), (NUEVA_YORK, "18:00", "18:15"))


@dataclass(frozen=True)
class Costes:
    comision_lado: float = 1.00         # $ por contrato y lado (Tradovate/Apex en micros ~0,5-1 $)
    ticks_normal: int = 1
    ticks_apertura: int = 2
    multiplicador: float = 1.0          # 2.0 = costes duplicados (prueba de robustez del paso 3)

    def ticks(self, instante: pd.Timestamp) -> float:
        idx = pd.DatetimeIndex([instante])
        abierta = any(en_ventana(idx, a, b, zona)[0] for zona, a, b in APERTURAS)
        return (self.ticks_apertura if abierta else self.ticks_normal) * self.multiplicador

    def comision(self, contratos: int) -> float:
        """Comisión de ida y vuelta."""
        return 2 * self.comision_lado * contratos * self.multiplicador
