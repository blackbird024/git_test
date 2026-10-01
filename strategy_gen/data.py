"""H1 bars from the Databento GC 15M file, difference back-adjusted across contract rolls.

Back-adjustment: at every roll the older history is shifted by (open of first new-contract bar -
close of last old-contract bar), so indicators see no artificial roll gaps. Price *differences*
inside one contract are unchanged, so trade P&L is unchanged. Trades are additionally forbidden
to hold across a roll bar (forced exit at the close of the bar before it).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NY = "America/New_York"


def load_h1(path: str | Path = ROOT / "data" / "XAUUSD_M15.csv") -> pd.DataFrame:
    m = pd.read_csv(path)
    m["ts"] = pd.to_datetime(m["timestamp"], utc=True)
    m = m.sort_values("ts").reset_index(drop=True)
    roll = m["instrument_id"].ne(m["instrument_id"].shift()) & m.index.to_series().gt(0)
    gap = np.where(roll, m["open"] - m["close"].shift(), 0.0)
    # adjustment applied to all bars BEFORE each roll = sum of later gaps
    adj = pd.Series(gap[::-1]).cumsum()[::-1].shift(-1, fill_value=0.0).to_numpy()
    for c in ("open", "high", "low", "close"):
        m[c] = m[c] + adj
    g = m.set_index("ts").resample("1h", label="left", closed="left")
    h = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "volume": g["volume"].sum(),
                      "instr_first": g["instrument_id"].first(), "instr_last": g["instrument_id"].last()})
    h = h.dropna(subset=["open"]).reset_index()
    h["roll_before"] = (h["instr_first"].ne(h["instr_last"].shift()) | h["instr_first"].ne(h["instr_last"]))
    h.loc[0, "roll_before"] = False
    h["ny"] = h["ts"].dt.tz_convert(NY)
    h["hour_ny"] = h["ny"].dt.hour
    h["dow"] = h["ny"].dt.dayofweek
    h["tdate"] = (h["ny"].dt.tz_localize(None) + pd.Timedelta(hours=7)).dt.normalize()  # session date
    return h.drop(columns=["instr_first", "instr_last"])


def splits(h: pd.DataFrame) -> dict:
    """Same calendar boundaries as the CRT study (TEST hold-out still untouched)."""
    b1 = pd.Timestamp("2020-03-01 05:00", tz="UTC")
    b2 = pd.Timestamp("2023-05-01 04:00", tz="UTC")
    return {"TRAIN": (h["ts"].iloc[0], b1), "VALIDATION": (b1, b2), "TEST": (b2, h["ts"].iloc[-1] + pd.Timedelta(hours=1))}


def shuffled_null(h: pd.DataFrame, seed: int) -> pd.DataFrame:
    """No-edge control: H1 bars rebuilt from randomly permuted bar 'shapes'.

    Each bar's (open gap, close-open, high-max(o,c), min(o,c)-low, volume) is shuffled across the
    whole history, then a price path is re-stitched. Timestamps, sessions, roll flags, the return
    distribution and volume distribution are kept; every temporal dependency (trend, mean
    reversion, seasonality, volatility clustering, volume-price link) is destroyed.
    """
    rng = np.random.default_rng(seed)
    o, hi, lo, c, v = (h[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    gap = np.r_[0.0, o[1:] - c[:-1]]
    body = c - o
    up = hi - np.maximum(o, c)
    dn = np.minimum(o, c) - lo
    p = rng.permutation(len(h))
    gap, body, up, dn, v = gap[p], body[p], up[p], dn[p], v[p]
    gap[0] = 0.0
    o2 = np.empty(len(h)); c2 = np.empty(len(h))
    last = c[0] - body[0]
    for i in range(len(h)):
        o2[i] = last + gap[i]
        c2[i] = o2[i] + body[i]
        last = c2[i]
    out = h.copy()
    out["open"], out["close"] = o2, c2
    out["high"] = np.maximum(o2, c2) + up
    out["low"] = np.minimum(o2, c2) - dn
    out["volume"] = v
    shift = max(0.0, 500.0 - out["low"].min())  # keep prices positive
    for k in ("open", "high", "low", "close"):
        out[k] += shift
    return out
