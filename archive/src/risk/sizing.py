"""Tamaño de posición: cuántos contratos comprar para arriesgar una cantidad fija de dólares.

Ejemplo sencillo (MNQ, 1 punto = 2 $):
    entrada 20.000, stop 19.970 -> 30 puntos de distancia
    pérdida por contrato si salta el stop = 30 * 2 $ + costes ≈ 62,50 $
    con 150 $ de riesgo -> 150 / 62,50 = 2,4 -> 2 contratos (siempre redondeamos hacia abajo)

Como la distancia al stop sale de la volatilidad (ATR o tamaño del rango), cuando el mercado
está nervioso el stop es más ancho y se compran menos contratos. Así el riesgo en dólares
es el mismo cada día: eso es "tamaño según volatilidad".
"""
import math

from src.config import Instrument


def loss_per_contract(inst: Instrument, entry: float, stop: float) -> float:
    """Dólares perdidos por contrato si salta el stop, incluyendo comisión y deslizamiento del stop."""
    distance = abs(entry - stop) + inst.slippage
    return distance * inst.point_value + inst.commission_rt


def contracts_for_risk(inst: Instrument, entry: float, stop: float, risk_usd: float) -> int:
    """Número entero de contratos cuyo riesgo no supera `risk_usd` (0 si ni uno cabe)."""
    per_contract = loss_per_contract(inst, entry, stop)
    if per_contract <= 0 or risk_usd <= 0:
        return 0
    return math.floor(risk_usd / per_contract + 1e-9)
