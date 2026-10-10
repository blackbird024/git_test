"""Estructura de 1 hora: pivotes confirmados y sesgo.

Swing high en la vela i: máximo estrictamente mayor que los máximos de las `left` velas anteriores y de las `right`
posteriores (swing low: espejo con mínimos). El pivote se CONFIRMA al cierre de la vela i+right; antes no existe.
Sesgo en el instante T (la apertura de la sesión, 9:30 ET): solo pivotes con confirmación <= T, calculados con velas
horarias cerradas <= T (la vela 9:00-10:00 está abierta a las 9:30 y no participa).
  alcista: los dos últimos swing highs confirmados ascendentes (estricto) Y los dos últimos swing lows ascendentes
  bajista: ambos descendentes
  neutral: cualquier otro caso, o menos de dos pivotes de cada tipo.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .bars import Hourly


@dataclass
class Pivots:
    hi_time: pd.DatetimeIndex      # inicio de la vela pivote
    hi_conf: pd.DatetimeIndex      # instante de confirmación (cierre de la vela i+right)
    hi_val: np.ndarray
    lo_time: pd.DatetimeIndex
    lo_conf: pd.DatetimeIndex
    lo_val: np.ndarray


def find_pivots(hb: Hourly, left=2, right=2) -> Pivots:
    H, L = hb.h, hb.l
    n = len(H)
    hi, lo = [], []
    for i in range(left, n - right):
        if all(H[i] > H[i - k] for k in range(1, left + 1)) and all(H[i] > H[i + k] for k in range(1, right + 1)):
            hi.append(i)
        if all(L[i] < L[i - k] for k in range(1, left + 1)) and all(L[i] < L[i + k] for k in range(1, right + 1)):
            lo.append(i)
    hi, lo = np.array(hi, int), np.array(lo, int)
    conf = hb.close_time
    return Pivots(hb.start[hi], conf[hi + right] if len(hi) else conf[:0], H[hi] if len(hi) else np.array([]),
                  hb.start[lo], conf[lo + right] if len(lo) else conf[:0], L[lo] if len(lo) else np.array([]))


def bias_at(p: Pivots, t: pd.Timestamp):
    """Sesgo con la información disponible en el instante t. Devuelve (sesgo, detalle)."""
    nh = int(p.hi_conf.searchsorted(t, side="right"))       # (sin .asi8: la unidad puede ser us o ns)
    nl = int(p.lo_conf.searchsorted(t, side="right"))
    det = {}
    if nh < 2 or nl < 2:
        return "neutral", {"motivo": "pivotes insuficientes", "n_highs": nh, "n_lows": nl}
    h1, h2 = p.hi_val[nh - 2], p.hi_val[nh - 1]
    l1, l2 = p.lo_val[nl - 2], p.lo_val[nl - 1]
    det = {"sh1": (str(p.hi_time[nh - 2]), float(h1)), "sh2": (str(p.hi_time[nh - 1]), float(h2)),
           "sl1": (str(p.lo_time[nl - 2]), float(l1)), "sl2": (str(p.lo_time[nl - 1]), float(l2)),
           "sh2_confirmado": str(p.hi_conf[nh - 1]), "sl2_confirmado": str(p.lo_conf[nl - 1])}
    if h2 > h1 and l2 > l1:
        return "alcista", det
    if h2 < h1 and l2 < l1:
        return "bajista", det
    return "neutral", det
