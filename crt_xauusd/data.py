"""Data loading, timezone normalisation, quality audit and causal bar features.

Conventions (documented in docs/DATA_REQUIREMENTS.md):
- Every bar is indexed by its OPEN time, stored as tz-aware UTC in column ``ts``.
- ``ny`` is the same instant in America/New_York (IANA, DST-aware). All session
  logic uses ``ny``; no fixed UTC offsets are used anywhere.
- A 15M bar is "closed" (usable) at ``ts + 15min``.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

NY = "America/New_York"
BAR = pd.Timedelta(minutes=15)


class DataMissingError(RuntimeError):
    pass


# ---------------------------------------------------------------- loading
def load_metadata(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise DataMissingError(f"Dataset metadata not found: {p}. See docs/DATA_REQUIREMENTS.md")
    with open(p) as f:
        meta = json.load(f)
    for k in ("source", "timestamp_tz", "price_side", "volume_type"):
        if k not in meta:
            raise ValueError(f"metadata missing required field '{k}'")
    return meta


def _localize(naive: pd.Series, tz_spec: str) -> pd.Series:
    """Convert naive wall-clock timestamps to UTC.

    ``tz_spec`` is an IANA name (e.g. 'UTC', 'Europe/Athens') or 'NY+7', the usual
    MT4/MT5 broker server clock (GMT+2 winter / GMT+3 summer, following US DST),
    which is exactly New York wall time + 7h all year.
    """
    if tz_spec.upper() == "NY+7":
        loc = (naive - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="NaT")
    else:
        loc = naive.dt.tz_localize(tz_spec, ambiguous="NaT", nonexistent="NaT")
    return loc.dt.tz_convert("UTC")


def read_raw(path: str | Path, meta: dict) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DataMissingError(f"Dataset not found: {p}. See docs/DATA_REQUIREMENTS.md")
    fmt = meta.get("format", "generic")
    if fmt == "mt5":
        # MetaTrader 5 export: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>
        raw = pd.read_csv(p, sep=None, engine="python")
        raw.columns = [c.strip("<>").lower() for c in raw.columns]
        naive = pd.to_datetime(raw["date"].astype(str) + " " + raw["time"].astype(str))
        vol_col = "tickvol" if meta["volume_type"] == "tick" else "vol"
        df = pd.DataFrame({"ts_naive": naive, "open": raw["open"], "high": raw["high"], "low": raw["low"],
                           "close": raw["close"], "volume": raw[vol_col]})
        if "spread" in raw:
            df["spread"] = raw["spread"] / float(meta.get("spread_units_per_price", 100))
    else:
        # generic: timestamp,open,high,low,close,volume[,spread] ; spread already in price units
        raw = pd.read_csv(p)
        raw.columns = [c.strip().lower() for c in raw.columns]
        ts = pd.to_datetime(raw["timestamp"], utc=False)
        if getattr(ts.dt, "tz", None) is not None:
            df = raw.drop(columns=["timestamp"]).assign(ts=ts.dt.tz_convert("UTC"))
            return _finish(df)
        df = raw.drop(columns=["timestamp"]).assign(ts_naive=ts)
    df["ts"] = _localize(df.pop("ts_naive"), meta["timestamp_tz"])
    return _finish(df)


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ts", "open", "high", "low", "close", "volume"] + (["spread"] if "spread" in df else [])
    return df[cols]


def aggregate_to_15m(df: pd.DataFrame) -> pd.DataFrame:
    """Data-construction helper only (e.g. a vendor ships 1-minute bars).

    The strategy never sees sub-15M information: sub-bars are collapsed into
    15M OHLCV before any logic runs.
    """
    g = df.set_index("ts").resample("15min", label="left", closed="left")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum()})
    if "spread" in df:
        out["spread"] = g["spread"].mean()
    return out.dropna(subset=["open"]).reset_index()


# ---------------------------------------------------------------- quality
def clean_and_audit(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    audit: dict = {"rows_raw": int(len(df))}
    audit["unparseable_or_dst_ambiguous_ts"] = int(df["ts"].isna().sum())
    df = df.dropna(subset=["ts"]).sort_values("ts")
    dup = df["ts"].duplicated(keep="first")
    audit["duplicate_ts_dropped"] = int(dup.sum())
    df = df[~dup]
    misaligned = (df["ts"].dt.minute % 15 != 0) | (df["ts"].dt.second != 0)
    audit["misaligned_ts_dropped"] = int(misaligned.sum())
    df = df[~misaligned]
    bad = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1)) \
        | (df["high"] < df["low"]) | df[["open", "high", "low", "close"]].isna().any(axis=1) \
        | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    audit["invalid_ohlc_dropped"] = int(bad.sum())
    df = df[~bad].reset_index(drop=True)
    audit["rows_clean"] = int(len(df))
    if len(df):
        audit["first_bar_utc"] = str(df["ts"].iloc[0])
        audit["last_bar_utc"] = str(df["ts"].iloc[-1])
        audit["zero_volume_bars"] = int((df["volume"] <= 0).sum())
        audit["volume_all_integer"] = bool(np.all(np.mod(df["volume"].to_numpy(), 1) == 0))
        dt = df["ts"].diff()
        audit["gaps_gt_15m"] = int((dt > BAR).sum())
        prev_wall = df["ts"].shift(1).dt.tz_convert(NY)
        scheduled = (prev_wall.dt.hour == 16) & (prev_wall.dt.minute == 45)  # daily break or weekend close
        audit["unexpected_gaps_gt_15m"] = int(((dt > BAR) & ~scheduled).sum())
        audit["has_spread_column"] = "spread" in df
        if "spread" in df:
            audit["spread_median_price"] = float(df["spread"].median())
            audit["spread_p95_price"] = float(df["spread"].quantile(0.95))
    return df, audit


# ---------------------------------------------------------------- features
def add_time_columns(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["ny"] = df["ts"].dt.tz_convert(cfg["time"]["canonical_tz"])
    anchor = pd.Timedelta(hours=cfg["time"]["h4_anchor_hour_ny"])
    wall = df["ny"].dt.tz_localize(None)
    # 4H buckets on New York WALL CLOCK anchored at 17:00 NY -> 17,21,01,05,09,13.
    # DST switches happen Sunday 02:00 NY while gold is closed, so no live bucket straddles one.
    df["h4_start_wall"] = (wall - anchor).dt.floor("4h") + anchor
    return df


def add_bar_features(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Causal features. Every value at row i uses rows <= i only (the bar itself is closed)."""
    df = df.copy()
    n = cfg["volume"]["lookback"]
    prev = df["volume"].shift(1)
    df["vol_sma_prev"] = prev.rolling(n, min_periods=n).mean()
    df["volume_ratio"] = df["volume"] / df["vol_sma_prev"]
    # percentile rank of current volume within the previous n bars (share of prior bars <= current)
    v = df["volume"].to_numpy(dtype=float)
    rank = np.full(len(v), np.nan)
    if len(v) > n:
        win = np.lib.stride_tricks.sliding_window_view(v[:-1], n)  # win[k] = v[k:k+n] -> prior bars of row k+n
        rank[n:] = 100.0 * (win <= v[n:, None]).mean(axis=1)
    df["volume_pctrank_prev"] = rank
    for q in sorted({vv["threshold"] for vv in _all_volume_variants(cfg).values() if vv["type"] == "percentile"}):
        df[f"vol_q{q:g}_prev"] = prev.rolling(n, min_periods=n).quantile(q / 100.0, interpolation="linear")
    dq = cfg["data_quality"]
    rng = df["high"] - df["low"]
    med = rng.shift(1).rolling(dq["abnormal_lookback_bars"], min_periods=20).median()
    df["abnormal_bar"] = (rng > dq["abnormal_range_multiple"] * med).fillna(False)
    if "spread" in df:
        smed = df["spread"].shift(1).rolling(dq["extreme_spread_lookback_bars"], min_periods=20).median()
        df["extreme_spread"] = (df["spread"] > dq["extreme_spread_multiple"] * smed).fillna(False)
    else:
        df["extreme_spread"] = False
    return df


def _all_volume_variants(cfg: dict) -> dict:
    return {"base": cfg["volume"]["base"], **cfg["volume"].get("sensitivity", {})}


def volume_passes(row, variant: dict) -> tuple[bool, float]:
    """Return (pass, measured value). NaN lookback -> fail (insufficient history)."""
    if variant["type"] == "ratio":
        val = row["volume_ratio"]
        return (bool(val >= variant["threshold"]) if np.isfinite(val) else False), float(val)
    if variant["type"] == "percentile":
        thr = row[f"vol_q{variant['threshold']:g}_prev"]
        return (bool(row["volume"] >= thr) if np.isfinite(thr) else False), float(thr)
    if variant["type"] == "none":
        return True, float("nan")
    raise ValueError(variant)


def build_h4(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    g = df.groupby("h4_start_wall", sort=True)
    h4 = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
        "volume": g["volume"].sum(), "n_bars": g.size(), "first_idx": g.apply(lambda x: x.index[0]),
        "last_idx": g.apply(lambda x: x.index[-1]),
    })
    anchor = cfg["time"]["h4_anchor_hour_ny"]
    # the 17:00 bucket contains the 17:00-18:00 daily maintenance break -> 12 bars expected
    expected = np.where(h4.index.hour == anchor, 12, 16)
    h4["complete"] = h4["n_bars"] >= expected
    # contiguity inside bucket
    h4["contiguous"] = [
        bool((df["ts"].iloc[a:b + 1].diff().dropna() == BAR).all()) for a, b in zip(h4["first_idx"], h4["last_idx"])
    ]
    return h4


def prepare(df_raw: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df, audit = clean_and_audit(df_raw)
    df = add_time_columns(df, cfg)
    df = add_bar_features(df, cfg)
    h4 = build_h4(df, cfg)
    audit["h4_buckets"] = int(len(h4))
    audit["h4_complete"] = int(h4["complete"].sum())
    return df, h4, audit
