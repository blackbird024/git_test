"""Simulador de ejecución intradía sobre velas de 1 minuto.

Reglas de ejecución (documentadas también en config/CONFIG_COSTES.yaml):
- Entrada a mercado en el minuto k: precio = apertura del primer minuto con operaciones ≥ k, más el deslizamiento.
- Entrada con orden stop (ruptura inmediata): se activa si el máximo (largo) alcanza el nivel; se llena al nivel o a la
  apertura si esta ya lo ha superado (hueco), más el deslizamiento. En el minuto de entrada, si la misma vela de 1 min
  toca también el stop-loss, se supone que lo tocó después de entrar (stop primero, conservador).
- Stop-loss: si la apertura de un minuto ya está más allá del stop, se ejecuta en la apertura (hueco); si no, al stop.
  Siempre con deslizamiento adverso.
- Objetivo (orden límite): solo se llena si el precio cruza el nivel en `limit_cross_ticks` ticks; sin deslizamiento.
  Si la apertura ya lo supera, se llena en la apertura.
- Si stop y objetivo caben en la misma vela de 1 min: stop primero.
- Salida por tiempo a mercado en la apertura del minuto `exit_k` (o el último cierre de la sesión), con deslizamiento.
- Si en el momento de entrar el precio ya está al otro lado del stop, la operación se cancela.
"""
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np

from execution_costs.costs import FutCost


@dataclass
class Order:
    side: int                    # +1 largo, -1 corto
    kind: str                    # "market" o "stop"
    k: int                       # minuto de sesión (0 = 9:30) desde el que la orden está activa
    stop: float
    target: Optional[float]      # None = sin objetivo
    exit_k: int                  # minuto de salida por tiempo
    level: float = np.nan        # nivel de activación para órdenes stop
    k_last: int = 390            # último minuto en que una orden stop puede activarse
    target_r: Optional[float] = None   # si se da, el objetivo se recalcula desde la entrada efectiva
    tag: str = ""


@dataclass
class Fill:
    date: object
    side: int
    entry_k: int
    entry: float
    stop: float
    target: float
    exit_k: int
    exit: float
    reason: str
    risk_pts: float              # distancia entrada efectiva → stop
    gross_pts: float             # resultado en puntos con deslizamiento incluido
    tag: str = ""

    def as_dict(self):
        return asdict(self)


def simulate(date, m: np.ndarray, close_min: int, o: Order, c: FutCost) -> Optional[Fill]:
    O, H, L, C = m[:, 0], m[:, 1], m[:, 2], m[:, 3]
    end = min(o.exit_k, close_min)
    s = o.side
    slip, tick = c.slip, c.tick
    # ── entrada
    k = o.k
    entry = None
    if o.kind == "market":
        while k < close_min and np.isnan(O[k]):
            k += 1
        if k >= end:
            return None
        entry = O[k] + s * slip
    else:
        last = min(o.k_last, end)
        while k < last:
            if not np.isnan(O[k]):
                if s == 1 and H[k] >= o.level:
                    entry = max(o.level, O[k]) + slip
                    break
                if s == -1 and L[k] <= o.level:
                    entry = min(o.level, O[k]) - slip
                    break
            k += 1
        if entry is None:
            return None
    stop = o.stop
    if s * (entry - stop) <= 0:
        return None                                  # el precio ya está más allá del stop: se cancela
    risk = s * (entry - stop)
    target = o.target
    if o.target_r is not None:
        target = entry + s * o.target_r * risk
    tgt_cross = c.limit_cross_ticks * tick
    ek = k
    # ── gestión minuto a minuto (el minuto de entrada incluido)
    j = k
    while j < end:
        if np.isnan(O[j]):
            j += 1
            continue
        first = j == ek
        tgt_ok = target is not None and not (first and o.kind == "stop")   # en la vela de entrada stop: sin objetivo
        if s == 1:
            if not first and O[j] <= stop:
                return _fill(date, o, ek, entry, stop, target, j, O[j] - slip, "stop_hueco", risk)
            if L[j] <= stop:
                return _fill(date, o, ek, entry, stop, target, j, stop - slip, "stop", risk)
            if tgt_ok:
                if not first and O[j] >= target:
                    return _fill(date, o, ek, entry, stop, target, j, O[j], "objetivo", risk)
                if H[j] >= target + tgt_cross:
                    return _fill(date, o, ek, entry, stop, target, j, target, "objetivo", risk)
        else:
            if not first and O[j] >= stop:
                return _fill(date, o, ek, entry, stop, target, j, O[j] + slip, "stop_hueco", risk)
            if H[j] >= stop:
                return _fill(date, o, ek, entry, stop, target, j, stop + slip, "stop", risk)
            if tgt_ok:
                if not first and O[j] <= target:
                    return _fill(date, o, ek, entry, stop, target, j, O[j], "objetivo", risk)
                if L[j] <= target - tgt_cross:
                    return _fill(date, o, ek, entry, stop, target, j, target, "objetivo", risk)
        j += 1
    # ── salida por tiempo
    if end < close_min:
        j = end
        while j < close_min and np.isnan(O[j]):
            j += 1
        if j < close_min:
            return _fill(date, o, ek, entry, stop, target, j, O[j] - s * slip, "tiempo", risk)
    j = close_min - 1
    while np.isnan(C[j]):
        j -= 1
    return _fill(date, o, ek, entry, stop, target, j, C[j] - s * slip, "cierre_sesion", risk)


def _fill(date, o, ek, entry, stop, target, xk, xp, reason, risk):
    return Fill(date, o.side, ek, entry, stop, np.nan if target is None else target, xk, xp, reason, risk,
                o.side * (xp - entry), o.tag)


def run(sessions, strategy, cost: FutCost, ctx=None, **params):
    """Ejecuta `strategy(session, ctx, **params) -> Order | None` en todas las sesiones. Devuelve lista de Fill.

    `ctx` contiene información conocida ANTES de la sesión (p. ej. indicadores diarios desplazados un día)."""
    out = []
    ctx = {} if ctx is None else ctx
    for s in sessions:
        o = strategy(s, ctx, **params)
        if o is None:
            continue
        f = simulate(s.date, s.m, s.close_min, o, cost)
        if f is not None:
            out.append(f)
    return out
