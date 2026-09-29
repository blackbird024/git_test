"""Tamaño de posición por riesgo fijo en % del saldo.

    riesgo_$            = saldo x riesgo_pct              (0,5 % -> 0,005)
    riesgo_por_contrato = distancia_al_stop (puntos) x valor del punto (MNQ: 2 $)
    contratos           = floor(riesgo_$ / riesgo_por_contrato)     (nunca fracciones)
Si el resultado es < 1, no hay operación (NO se redondea hacia arriba).
"""
import math


def contratos(saldo: float, riesgo_pct: float, distancia_puntos: float, valor_punto: float,
              maximo: int | None = None) -> int:
    if saldo <= 0 or riesgo_pct <= 0 or distancia_puntos <= 0 or valor_punto <= 0:
        return 0
    n = math.floor(saldo * riesgo_pct / (distancia_puntos * valor_punto) + 1e-9)
    return min(n, maximo) if maximo is not None else n
