"""Ejecución de una operación sobre velas (normalmente de 1 minuto), con reglas conservadoras:

  1. La señal se calcula con una vela CERRADA; la entrada es en la APERTURA de la vela siguiente
     (función indice_entrada), con deslizamiento en contra.
  2. Si en una misma vela se tocan el stop y el objetivo, cuenta SIEMPRE como pérdida.
  3. Si la vela abre ya más allá del stop (hueco), se sale en la apertura, con deslizamiento.
  4. El objetivo es una orden límite: se llena exactamente a su precio, sin deslizamiento.
  5. Salida por tiempo en la apertura de la primera vela a partir de la hora límite, con deslizamiento.

Además se guarda el "recorrido" del P&L (mejor y peor precio de cada vela, en ese orden, que es el que más
perjudica a un drawdown trailing) para simular las reglas de Apex.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.engine.costes import Costes


@dataclass
class Operacion:
    direccion: int
    contratos: int
    t_senal: pd.Timestamp
    t_entrada: pd.Timestamp
    entrada: float
    stop: float
    objetivo: float | None
    t_salida: pd.Timestamp | None = None
    salida: float | None = None
    motivo: str = ""
    bruto: float = 0.0
    comision: float = 0.0
    neto: float = 0.0
    riesgo_usd: float = 0.0
    recorrido: list = field(default_factory=list)

    @property
    def r(self) -> float:
        return self.neto / self.riesgo_usd if self.riesgo_usd else 0.0


def indice_entrada(velas: pd.DataFrame, i_senal: int) -> int | None:
    """La entrada es la vela SIGUIENTE a la de la señal. Devuelve su posición o None si no existe."""
    return i_senal + 1 if i_senal + 1 < len(velas) else None


def ejecutar(velas: pd.DataFrame, i_senal: int, direccion: int, stop: float, objetivo: float | None,
             contratos: int, t_limite: pd.Timestamp, tick: float, valor_punto: float,
             costes: Costes) -> Operacion | None:
    """Simula una operación que se decide al cierre de la vela `i_senal`. None si no se puede entrar
    (no hay vela siguiente, ya es la hora límite o la entrada queda al otro lado del stop)."""
    i = indice_entrada(velas, i_senal)
    if i is None or velas.index[i] >= t_limite:
        return None
    O, H, L = velas.open.to_numpy(), velas.high.to_numpy(), velas.low.to_numpy()
    t = velas.index
    d = direccion
    entrada = O[i] + d * costes.ticks(t[i]) * tick
    if (entrada - stop) * d <= 0 or (objetivo is not None and (objetivo - entrada) * d <= 0):
        return None
    pv = valor_punto * contratos
    op = Operacion(d, contratos, t[i_senal], t[i], entrada, stop, objetivo,
                   riesgo_usd=abs(entrada - stop) * pv + costes.comision(contratos))
    c_lado = costes.comision(contratos) / 2
    pnl = lambda px: (px - entrada) * d * pv - c_lado  # noqa: E731  (abierto, ya pagada la entrada)
    op.recorrido.append(-c_lado)

    def cerrar(k, px, motivo):
        op.t_salida, op.salida, op.motivo = t[k], px, motivo
        op.bruto = (px - entrada) * d * pv
        op.comision = costes.comision(contratos)
        op.neto = op.bruto - op.comision
        op.recorrido.append(op.neto)
        return op

    for k in range(i, len(velas)):
        if t[k] >= t_limite:
            return cerrar(k, O[k] - d * costes.ticks(t[k]) * tick, "tiempo")
        mejor, peor = (H[k], L[k]) if d == 1 else (L[k], H[k])
        toca_stop = peor <= stop if d == 1 else peor >= stop
        toca_obj = objetivo is not None and (mejor >= objetivo if d == 1 else mejor <= objetivo)
        if toca_stop:                                    # también si toca el objetivo: cuenta como pérdida
            base = min(stop, O[k]) if d == 1 else max(stop, O[k])
            # Para el drawdown: primero lo favorable de la vela (sin pasar del objetivo), después el stop.
            favorable = mejor
            if objetivo is not None:
                favorable = min(mejor, objetivo) if d == 1 else max(mejor, objetivo)
            op.recorrido.append(pnl(favorable))
            return cerrar(k, base - d * costes.ticks(t[k]) * tick, "stop")
        if toca_obj:
            op.recorrido.append(pnl(peor))
            return cerrar(k, objetivo, "objetivo")
        op.recorrido.append(pnl(mejor))
        op.recorrido.append(pnl(peor))
    return cerrar(len(velas) - 1, velas.close.iloc[-1] - d * costes.ticks(t[-1]) * tick, "fin_de_datos")


def a_tabla(operaciones: list[Operacion]) -> pd.DataFrame:
    filas = [{k: v for k, v in o.__dict__.items() if k != "recorrido"} | {"r": o.r} for o in operaciones]
    return pd.DataFrame(filas)


def contratos_por_riesgo(riesgo_usd: float, distancia: float, valor_punto: float, maximo: int) -> int:
    """Contratos para arriesgar `riesgo_usd` con un stop a `distancia` puntos (0 si no cabe ni uno)."""
    if distancia <= 0:
        return 0
    n = int(np.floor(riesgo_usd / (distancia * valor_punto) + 1e-9))
    return min(n, maximo)
