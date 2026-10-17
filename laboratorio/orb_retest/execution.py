"""Simulación de la ejecución sobre velas de 1 min (mismas convenciones que backtests/intraday.py del laboratorio).

- Entrada a mercado en la apertura del primer minuto con datos >= signal_k (nunca al cierre de la vela de señal),
  con deslizamiento adverso. Si ese minuto es posterior a last_entry_k, no se opera.
- SL = mínimo de la vela de retesteo − 1 tick (largo) / máximo + 1 tick (corto). Si la entrada ejecutada queda al
  otro lado del SL (o a distancia 0), se descarta.
- R = |entrada − SL|. TP = entrada ± tp_r·R redondeado a la rejilla de ticks en el sentido DESFAVORABLE (más lejos).
- Gestión minuto a minuto desde el minuto de entrada (incluido):
    1. hueco: si la apertura de un minuto (posterior al de entrada) ya está más allá del SL → sale en la apertura
       con deslizamiento (peor precio razonable, no el nivel del stop);
    2. SL tocado → sale en el SL con deslizamiento; si en ese mismo minuto también se alcanza el TP, se cuenta
       como AMBIGUO y se aplica SL primero (conservador);
    3. hueco a favor más allá del TP → se llena en el TP (supuesto conservador: no se cobra la mejora del hueco);
    4. TP: solo si el precio CRUZA el nivel en tp_cross_ticks ticks; sin deslizamiento (orden límite).
- Cierre obligatorio a mercado en la apertura del minuto flat_k (15:55, o 5 min antes de una media jornada).
"""
import math
from dataclasses import dataclass, asdict

import numpy as np

from .config import Costs, Strategy
from .signals import Signal


@dataclass
class Trade:
    side: int
    entry_k: int
    entry: float
    sl: float
    tp: float
    r_pts: float
    exit_k: int
    exit: float
    reason: str               # tp | sl | sl_hueco | tiempo
    ambiguous: bool           # SL y TP alcanzables en el mismo minuto (se aplicó SL primero)
    gross_pts: float          # resultado en puntos, deslizamiento incluido

    def as_dict(self):
        return asdict(self)


def round_tp(x: float, side: int, tick: float) -> float:
    q = x / tick
    return (math.ceil(q - 1e-9) if side == 1 else math.floor(q + 1e-9)) * tick


def simulate(sig: Signal, m: np.ndarray, close_min: int, st: Strategy, c: Costs):
    """Devuelve (Trade | None, motivo)."""
    O, H, L = m[:, 0], m[:, 1], m[:, 2]
    tick = c.tick
    flat_k = min(st.flat_k, close_min - 5)
    k = sig.signal_k
    while k < close_min and np.isnan(O[k]):
        k += 1
    if k >= close_min or k > st.last_entry_k or k >= flat_k:
        return None, "sin_minuto_ejecutable"
    s = sig.side
    entry = O[k] + s * c.slip_ticks_entry * tick
    sl = round((sig.retest_low - st.stop_offset_ticks * tick) / tick) * tick if s == 1 else \
        round((sig.retest_high + st.stop_offset_ticks * tick) / tick) * tick
    r_pts = s * (entry - sl)
    if r_pts <= 1e-9:
        return None, "entrada_al_otro_lado_del_stop"
    tp = round_tp(entry + s * st.tp_r * r_pts, s, tick)
    cross = c.tp_cross_ticks * tick
    sslip, tslip = c.slip_ticks_stop * tick, c.slip_ticks_time * tick

    def out(j, px, why, amb=False):
        return Trade(s, k, entry, sl, tp, r_pts, j, px, why, amb, s * (px - entry)), "operacion"

    for j in range(k, flat_k):
        if np.isnan(O[j]):
            continue
        first = j == k
        if not first and s * (O[j] - sl) <= 0:
            return out(j, O[j] - s * sslip, "sl_hueco")
        hit_sl = (L[j] <= sl) if s == 1 else (H[j] >= sl)
        hit_tp = (H[j] >= tp + cross) if s == 1 else (L[j] <= tp - cross)
        if hit_sl:
            return out(j, sl - s * sslip, "sl", amb=bool(hit_tp))
        if not first and s * (O[j] - tp) >= 0:
            return out(j, tp, "tp")
        if hit_tp:
            return out(j, tp, "tp")
    j = flat_k
    while j < close_min and np.isnan(O[j]):
        j += 1
    if j < close_min:
        return out(j, O[j] - s * tslip, "tiempo")
    C = m[:, 3]
    j = close_min - 1
    while np.isnan(C[j]):
        j -= 1
    return out(j, C[j] - s * tslip, "tiempo")


def cost_usd_per_contract(c: Costs) -> float:
    """Comisión ida y vuelta (el deslizamiento ya está dentro de los precios de ejecución)."""
    return 2 * c.commission_per_side


def contracts_for(risk_budget: float, est_r_pts: float, c: Costs, max_contracts: int) -> int:
    """floor(presupuesto / pérdida estimada por contrato). La pérdida estimada incluye la distancia al stop, el
    deslizamiento esperado de entrada y de stop y la comisión ida y vuelta. 0 = no cabe ningún contrato."""
    loss = (est_r_pts + (c.slip_ticks_entry + c.slip_ticks_stop) * c.tick) * c.point_value + cost_usd_per_contract(c)
    if loss <= 0:
        return 0
    return int(min(max_contracts, math.floor(risk_budget / loss + 1e-9)))
