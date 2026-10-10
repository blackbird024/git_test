"""Dataset SINTÉTICO para comprobar el funcionamiento técnico. NO son datos de mercado: paseo aleatorio con semilla fija.
Nunca usar sus resultados como evidencia de nada."""
from pathlib import Path

import numpy as np
import pandas as pd


def synthetic_5m(start="2024-01-01", end="2024-06-30", seed=7, price=17000.0, tick=0.25):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(f"{start} 18:00", f"{end} 17:00", freq="5min", tz="America/New_York")
    tod = idx.hour * 60 + idx.minute
    wd = idx.dayofweek
    open_ = ~((tod >= 17 * 60) & (tod < 18 * 60))                       # pausa diaria 17:00-18:00
    open_ &= ~(wd == 5) & ~((wd == 6) & (tod < 18 * 60)) & ~((wd == 4) & (tod >= 17 * 60))
    idx = idx[open_]
    n = len(idx)
    vol = np.where((idx.hour * 60 + idx.minute >= 570) & (idx.hour * 60 + idx.minute < 960), 6.0, 2.5)
    steps = rng.standard_t(4, n) * vol * 0.6 + 0.05
    c = price + np.cumsum(steps)
    o = np.r_[price, c[:-1]]
    hi = np.maximum(o, c) + np.abs(rng.normal(0, vol * 0.5, n))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, vol * 0.5, n))
    r = lambda x: np.round(x / tick) * tick
    df = pd.DataFrame({"open": r(o), "high": r(hi), "low": r(lo), "close": r(c)}, index=idx)
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    df["volume"] = rng.integers(50, 500, n)
    df["contract"] = "SINTETICO"
    return df


def to_csv(df: pd.DataFrame, path):
    out = df.copy()
    out.insert(0, "timestamp", out.index.map(lambda t: t.isoformat()))
    out.to_csv(path, index=False)
    return Path(path)


def write_demo(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return to_csv(synthetic_5m(), path)
