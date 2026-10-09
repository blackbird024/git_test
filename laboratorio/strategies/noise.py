"""A3 · Auditoría de la "zona de ruido" (Zarattini, Aziz y Barbon, 2024) tal como se implementó en
alpaca/mnq_intraday_lab.py (función `noise`, parámetros por defecto: lookback 14, decisión cada 30 min, salida con
la "media del día", banda ×1,0). Reglas originales, sin cambiar parámetros:

- Ruido a la hora h = media de |cierre_h / apertura − 1| de las 14 sesiones anteriores (velas de 5 min).
- Banda superior = max(apertura, cierre de ayer) × (1 + ruido); inferior = min(apertura, cierre de ayer) × (1 − ruido).
- Cada 30 min (cierre de las velas de 9:55, 10:25, …): si largo y el cierre < max(banda sup., media típica del día) → sale;
  si corto y cierre > min(banda inf., media) → sale. Sin posición: cierre > banda sup. → largo; < banda inf. → corto.
- Ejecución en la apertura de la vela siguiente. Cierre forzoso al final de la sesión. Sin stop-loss.

Diferencias de ESTA reimplementación respecto a la original (deliberadas, para medir el efecto de la ejecución):
- Ejecución con el deslizamiento y la comisión del modelo de costes en lugar de 1 punto fijo por operación.
- La salida final se hace en la apertura de las 15:55 a mercado (no al cierre exacto de las 16:00).
- Las sesiones se toman del calendario XNYS y las velas de 5 min se construyen desde las de 1 min; la original exigía
  78 velas de 5 min y descartaba medias jornadas y días con huecos; aquí también se exigen 78 velas para operar.
"""
import numpy as np

from backtests.intraday import Fill
from data.loaders import bars5


def noise_trades(sessions, cost, lookback=14, step=6, band_mult=1.0):
    out = []
    hist = []                                   # (perfil de |c/o-1| de 78 velas, cierre) de sesiones completas
    prev_close = None
    for s in sessions:
        b = bars5(s)
        full = len(b) == 78 and not np.isnan(b[:, 3]).any()
        if full and len(hist) >= lookback and prev_close is not None:
            out += _day(s, b, np.mean([h for h in hist[-lookback:]], axis=0) * band_mult, prev_close, cost, step)
        if full:
            hist.append(np.abs(b[:, 3] / b[0, 0] - 1))
        last = b[~np.isnan(b[:, 3])]
        prev_close = last[-1, 3] if len(last) else prev_close
    return out


def _day(s, b, sigma, pc, c, step):
    o = b[0, 0]
    ub = max(o, pc) * (1 + sigma)
    lb = min(o, pc) * (1 - sigma)
    typ = (b[:, 1] + b[:, 2] + b[:, 3]) / 3
    twap = np.cumsum(typ) / np.arange(1, 79)
    slip = c.slip
    fills, pos, entry, ek = [], 0, 0.0, 0
    for k in range(step - 1, 77, step):
        cl = b[k, 3]
        px = b[k + 1, 0]
        if pos == 1 and cl < max(ub[k], twap[k]):
            fills.append(_f(s, 1, ek, entry, 5 * (k + 1), px - slip)); pos = 0
        elif pos == -1 and cl > min(lb[k], twap[k]):
            fills.append(_f(s, -1, ek, entry, 5 * (k + 1), px + slip)); pos = 0
        if pos == 0 and cl > ub[k]:
            pos, entry, ek = 1, px + slip, 5 * (k + 1)
        elif pos == 0 and cl < lb[k]:
            pos, entry, ek = -1, px - slip, 5 * (k + 1)
    if pos:
        px = b[77, 0]
        fills.append(_f(s, pos, ek, entry, 385, px - pos * slip))
    return fills


def _f(s, side, ek, entry, xk, xp):
    return Fill(s.date, side, ek, entry, np.nan, np.nan, xk, xp, "regla", np.nan, side * (xp - entry), "noise")
