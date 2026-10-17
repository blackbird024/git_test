"""Rango de apertura, velas de 5 min y detección ruptura → retesteo → confirmación, sin mirar el futuro.

Reglas (MNQ_ORB_RETEST_v1):
  ORH/ORL = máximo/mínimo de los minutos 0-14 (9:30:00-9:44:59 ET). Disponibles desde el minuto 15 (9:45).
  Ruptura: primera vela de 5 min COMPLETA, desde la de 9:45, con close > ORH (largo) o close < ORL (corto).
  Retesteo (largo): en las `retest_bars` velas siguientes, la primera vela que
      vuelve a la zona  → low <= ORH + tol
      no se hunde       → low >= ORH - tol
      cierra fuera      → close > ORH
      es alcista        → close > open
  Corto: espejo con ORL. La primera vela que cumple TODO genera la señal al cierre. Si ninguna cumple, se cancela el día
  (solo cuenta la primera ruptura; no se busca otra).
  La señal debe permitir entrar como muy tarde en el minuto `last_entry_k` (11:30).
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import Strategy

EPS = 1e-9


@dataclass
class Signal:
    side: int                 # +1 largo, -1 corto
    orh: float
    orl: float
    breakout_bar: int         # índice de la vela de 5 min de ruptura
    retest_bar: int           # índice de la vela de confirmación
    signal_k: int             # minuto en que se conoce la señal (cierre de la vela) = primer minuto ejecutable
    retest_high: float
    retest_low: float
    signal_close: float


def opening_range(m: np.ndarray, st: Strategy):
    """(ORH, ORL, minutos con datos) o None si faltan datos."""
    x = m[: st.or_minutes]
    ok = ~np.isnan(x[:, 0])
    if ok.sum() < st.min_or_minutes_with_data or np.isnan(x[0, 0]):
        return None
    return float(np.nanmax(x[:, 1])), float(np.nanmin(x[:, 2])), int(ok.sum())


def bars(m: np.ndarray, close_min: int, bar_minutes: int = 5) -> np.ndarray:
    """Velas de N min alineadas a 9:30 construidas solo con las velas de 1 min de su propio bloque. NaN si vacío."""
    n = close_min // bar_minutes
    out = np.full((n, 4), np.nan)
    for b in range(n):
        x = m[bar_minutes * b: bar_minutes * b + bar_minutes]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            y = x[ok]
            out[b] = (y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3])
    return out


def detect(m: np.ndarray, close_min: int, st: Strategy, tick: float = 0.25):
    """Devuelve (Signal | None, motivo). Solo usa velas cuyo cierre es anterior al minuto de señal."""
    r = opening_range(m, st)
    if r is None:
        return None, "rango_incompleto"
    orh, orl, _ = r
    B = bars(m, close_min, st.bar_minutes)
    tol = st.tol_ticks * tick
    first = st.or_minutes // st.bar_minutes            # primera vela tras el rango (9:45)
    for b in range(first, len(B)):
        if (b + 1) * st.bar_minutes > st.last_entry_k:
            return None, "sin_ruptura"
        o, h, l, c = B[b]
        if np.isnan(c):
            continue
        side = 1 if c > orh + EPS else -1 if c < orl - EPS else 0
        if side == 0:
            continue
        # primera ruptura válida encontrada: se busca el retesteo en las velas siguientes
        for j in range(b + 1, min(b + 1 + st.retest_bars, len(B))):
            sk = (j + 1) * st.bar_minutes
            if sk > st.last_entry_k:
                return None, "retesteo_despues_de_hora_limite"
            o2, h2, l2, c2 = B[j]
            if np.isnan(c2):
                continue
            if side == 1:
                ok = (l2 <= orh + tol + EPS) and (l2 >= orh - tol - EPS) and (c2 > orh + EPS) and (c2 > o2 + EPS)
            else:
                ok = (h2 >= orl - tol - EPS) and (h2 <= orl + tol + EPS) and (c2 < orl - EPS) and (c2 < o2 - EPS)
            if ok:
                return Signal(side, orh, orl, b, j, sk, float(h2), float(l2), float(c2)), "senal"
        return None, "sin_retesteo_valido"
    return None, "sin_ruptura"
