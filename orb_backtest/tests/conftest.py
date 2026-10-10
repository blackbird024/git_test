"""Fixtures sintéticas con resultados conocidos de antemano."""
from dataclasses import replace
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from orb_backtest.bars import SessionBars
from orb_backtest.config import load
from orb_backtest.structure import Pivots

TZ = "America/New_York"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg():
    c = load(ROOT / "orb_backtest" / "configs" / "config.example.yaml")
    c.costs = replace(c.costs, commission_per_side=0.0, slippage_ticks_per_side=0, limit_fill_ticks_through=1)
    return c


def make_session(date="2024-03-05", bars=None, base=100.0, flat=time(15, 55), drop=()):
    """Sesión 9:30-15:55 con velas planas en `base`; rango 9:30-10:25: máximo 101, mínimo 99 (vela de 9:30).
    `bars`: {"HH:MM": (o, h, l, c)} sustituye velas concretas; las demás son planas en el cierre anterior.
    `drop`: horas sin vela."""
    idx = pd.date_range(f"{date} 09:30", f"{date} 15:55", freq="5min", tz=TZ)
    bars = bars or {}
    m, last = {}, base
    for t in idx:                                   # velas no indicadas: planas en el último cierre (sin huecos)
        k = t.strftime("%H:%M")
        if k == "09:30":
            m[k] = [100.0, 101.0, 99.0, 100.0]
        elif k in bars:
            m[k] = list(bars[k])
        else:
            m[k] = [last] * 4
        last = m[k][3]
    keep = [t for t in idx if t.strftime("%H:%M") not in drop]
    arr = np.array([m[t.strftime("%H:%M")] for t in keep], float)
    return SessionBars(pd.Timestamp(date), pd.DatetimeIndex(keep), arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], flat)


def pivots(kind="alcista", day="2024-03-05"):
    """Pivotes confirmados el día anterior que producen el sesgo pedido."""
    t = pd.Timestamp(f"{day} 03:00", tz=TZ) - pd.Timedelta(days=1)
    times = pd.DatetimeIndex([t, t + pd.Timedelta(hours=5)])
    conf = times + pd.Timedelta(hours=3)
    hi = {"alcista": [100.0, 105.0], "bajista": [105.0, 100.0], "neutral": [100.0, 105.0]}[kind]
    lo = {"alcista": [90.0, 95.0], "bajista": [95.0, 90.0], "neutral": [95.0, 90.0]}[kind]
    return Pivots(times, conf, np.array(hi), times, conf, np.array(lo))


LONG_SETUP = {                      # ruptura 10:30 (cierre 101.5); 10:35 lejos del nivel; retesteo 10:40 a 1 tick
    "10:30": (100.0, 101.75, 100.0, 101.5),
    "10:35": (101.5, 102.5, 101.75, 102.25),    # mínimo a 3 ticks de OR_high: no es retesteo
    "10:40": (102.25, 102.25, 100.75, 101.5),   # mínimo 100.75 = OR_high − 1 tick, cierre por encima
    "10:45": (101.5, 101.5, 101.5, 101.5),      # apertura de entrada 101.5
}
SHORT_SETUP = {
    "10:30": (100.0, 100.0, 98.25, 98.5),
    "10:35": (98.25, 98.25, 97.5, 97.75),       # máximo a 3 ticks de OR_low: no es retesteo
    "10:40": (97.75, 99.25, 97.75, 98.5),       # máximo 99.25 = OR_low + 1 tick, cierre por debajo
    "10:45": (98.5, 98.5, 98.5, 98.5),
}
