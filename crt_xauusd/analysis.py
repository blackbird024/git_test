"""Temporal splits, walk-forward and descriptive regime analysis (never used as filters)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import summarize

NY = "America/New_York"


def split_boundaries(df: pd.DataFrame, cfg: dict) -> dict:
    t0, t1 = df["ts"].iloc[0], df["ts"].iloc[-1]
    s = cfg["splits"]

    def snap(t):
        ny = t.tz_convert(NY)
        return pd.Timestamp(year=ny.year, month=ny.month, day=1, tz=NY).tz_convert("UTC")

    b1 = snap(t0 + (t1 - t0) * s["train"])
    b2 = snap(t0 + (t1 - t0) * (s["train"] + s["validation"]))
    return {"TRAIN": (t0, b1), "VALIDATION": (b1, b2), "TEST": (b2, t1 + pd.Timedelta(minutes=15))}


def assign_split(trades: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    t = trades.copy()
    t["split"] = None
    for name, (a, b) in bounds.items():
        t.loc[(t["signal_time"] >= a) & (t["signal_time"] < b), "split"] = name
    return t


def walk_forward(groups: dict[str, pd.DataFrame], span: tuple, cfg: dict) -> pd.DataFrame:
    """Rolling IS/OOS windows over ``span`` for the single frozen BASE rule.

    Nothing is fitted (there is one hypothesis and no free parameter), so IS and OOS are both
    reported to check temporal stability rather than parameter generalisation.
    """
    w = cfg["walk_forward"]
    a, end = span
    rows, start, k = [], a, 0
    while True:
        is_end = start + pd.DateOffset(months=w["is_months"])
        if is_end >= end:
            break
        oos_end = min(is_end + pd.DateOffset(months=w["oos_months"]), end)
        for g, t in groups.items():
            ins = t[(t["signal_time"] >= start) & (t["signal_time"] < is_end)] if len(t) else t
            oos = t[(t["signal_time"] >= is_end) & (t["signal_time"] < oos_end)] if len(t) else t
            si, so = summarize(ins), summarize(oos)
            rows.append({"window": k, "is_start": start, "is_end": is_end, "oos_end": oos_end, "group": g,
                         "is_trades": si["trades"], "is_expectancy_R": si.get("expectancy_R"),
                         "oos_trades": so["trades"], "oos_expectancy_R": so.get("expectancy_R"),
                         "oos_total_R": so.get("total_R"), "oos_pf": so.get("profit_factor"),
                         "oos_win_rate": so.get("win_rate"), "oos_max_dd_R": so.get("max_drawdown_R")})
        start = start + pd.DateOffset(months=w["step_months"])
        k += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- regimes (descriptive only)
def regime_features(df: pd.DataFrame, h4: pd.DataFrame, cfg: dict) -> tuple[pd.Series, pd.Series]:
    r = cfg["regimes"]
    ok = h4[h4["complete"]]
    rng = ok["high"] - ok["low"]
    med_prior = rng.shift(1).rolling(r["vol_ratio_lookback_4h"], min_periods=10).median()
    vol_ratio = (rng / med_prior).rename("ref_range_vs_median")  # indexed by ref bucket start (wall)
    # trading date = NY wall date of (ts + 7h) so the session opening at 18:00 belongs to the next date
    wall = df["ny"].dt.tz_localize(None)
    tdate = (wall + pd.Timedelta(hours=7)).dt.normalize()
    closes = df.groupby(tdate)["close"].last()
    n = r["trend_lookback_days"]
    chg = closes.diff().abs().rolling(n).sum()
    er = ((closes - closes.shift(n)).abs() / chg).shift(1).rename("trend_efficiency_ratio")  # prior days only
    return vol_ratio, er


def add_regimes(t: pd.DataFrame, vol_ratio: pd.Series, er: pd.Series, cfg: dict) -> pd.DataFrame:
    if len(t) == 0:
        return t
    t = t.copy()
    r = cfg["regimes"]
    t["ref_range_vs_median"] = t["ref_start_ny"].map(vol_ratio)
    wall = t["signal_time"].dt.tz_convert(NY).dt.tz_localize(None)
    t["trend_efficiency_ratio"] = ((wall + pd.Timedelta(hours=7)).dt.normalize()).map(er)
    ve, te = r["vol_regime_edges"], r["trend_er_edges"]
    t["vol_regime"] = pd.cut(t["ref_range_vs_median"], [-np.inf, ve[0], ve[1], np.inf],
                             labels=["low", "normal", "high"])
    t["trend_regime"] = pd.cut(t["trend_efficiency_ratio"], [-np.inf, te[0], te[1], np.inf],
                               labels=["range", "mixed", "trend"])
    ny = t["entry_time"].dt.tz_convert(NY)
    t["weekday"] = ny.dt.day_name()
    t["year"] = ny.dt.year
    t["month"] = ny.dt.month
    return t


def regime_tables(t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if len(t) == 0:
        return {}
    t = t.copy()
    q = lambda col: pd.qcut(t[col], 4, duplicates="drop")  # descriptive quartiles of observed trades
    dims = {
        "vol_regime": t["vol_regime"], "trend_regime": t["trend_regime"], "weekday": t["weekday"],
        "year": t["year"], "month": t["month"], "kz": t["kz"], "direction": t["direction"],
        "sweep_depth_pct_range_q": q("sweep_depth_pct_range"), "sweep_depth_q": q("sweep_depth"),
        "volume_ratio_q": q("volume_ratio"), "engulf_body_ratio_q": q("engulf_body_ratio"),
        "confirm_body_ratio_q": q("confirm_body_ratio"), "stop_distance_q": q("stop_distance"),
        "minutes_exec_start_to_sweep_q": q("minutes_exec_start_to_sweep"), "sweep_in_kz": t["sweep_in_kz"],
        "confirm_close_back_inside_ref_range": t["confirm_close_back_inside_ref_range"],
    }
    out = {}
    for name, key in dims.items():
        g = t.groupby(key.astype(str))["R"]
        out[name] = pd.DataFrame({"trades": g.size(), "expectancy_R": g.mean(), "total_R": g.sum(),
                                  "win_rate": g.apply(lambda x: (x > 0).mean())})
    return out
