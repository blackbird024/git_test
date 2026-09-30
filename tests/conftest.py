"""Test fixtures. SYNTHETIC data lives only here and only tests code paths; it is never used
for any research result and is never written to reports/ or data/."""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from crt_xauusd.config import load_config

NY = "America/New_York"


@pytest.fixture
def cfg():
    return copy.deepcopy(load_config())


def trading_bar_times_ny(start: str, end: str) -> pd.DatetimeIndex:
    """15M bar open times of a gold CFD week: Sun 18:00 -> Fri 17:00 NY, daily break 17:00-18:00."""
    idx = pd.date_range(start, end, freq="15min", tz=NY, inclusive="left")
    wd, hr = idx.dayofweek, idx.hour
    keep = (hr != 17)
    keep &= ~(wd == 5)                       # Saturday closed
    keep &= ~((wd == 6) & (hr < 18))        # Sunday before 18:00 closed
    keep &= ~((wd == 4) & (hr >= 17))       # Friday after 17:00 closed
    return idx[keep]


def synthetic_random_walk(start="2024-01-07 18:00", end="2024-03-30", seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = trading_bar_times_ny(start, end)
    n = len(t)
    o = np.empty(n); c = np.empty(n)
    p = 2000.0
    for i in range(n):
        o[i] = p
        c[i] = p + rng.normal(0, 1.5)
        p = c[i]
    h = np.maximum(o, c) + np.abs(rng.normal(0, 0.8, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 0.8, n))
    v = np.round(rng.lognormal(6, 0.5, n))
    return pd.DataFrame({"ts": t.tz_convert("UTC"), "open": o, "high": h, "low": l, "close": c, "volume": v})


def scenario_frame(overrides: dict[str, tuple], base_price=2660.0, day="2024-01-10") -> pd.DataFrame:
    """Flat, quiet 15M bars from previous day 18:00 NY to `day` 13:00 NY, with explicit bars
    overridden by NY wall time 'HH:MM' -> (open, high, low, close, volume)."""
    d = pd.Timestamp(day, tz=NY)
    t = pd.date_range(d - pd.Timedelta(hours=6), d + pd.Timedelta(hours=13), freq="15min", inclusive="left")
    rows = []
    for ts in t:
        key = ts.strftime("%H:%M") if ts.date() == d.date() else None
        if key in overrides:
            o, h, l, c, v = overrides[key]
        else:
            o, h, l, c, v = base_price, base_price + 1, base_price - 1, base_price, 100
        rows.append((ts.tz_convert("UTC"), o, h, l, c, v))
    return pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
