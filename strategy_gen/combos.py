"""Pre-registered combinations of 5 literature-motivated gold strategies (docs/COMBO_PREREG.md).

    python -m strategy_gen.combos
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from .data import ROOT

OUT = ROOT / "reports" / "combos"
NY = "America/New_York"
COST_SIDE = 0.185            # USD/oz per side (half of the 0.37 round trip used everywhere)
TARGET_VOL, VOL_LB, W_CAP = 0.10, 60, 3.0
SPLITS = {"TRAIN": ("2010-06-07", "2020-03-01"), "VALIDATION": ("2020-03-01", "2023-05-01"),
          "TEST": ("2023-05-01", "2026-09-29")}
N_PERM, SEED = 500, 20261001


def load_h1_ratio() -> pd.DataFrame:
    m = pd.read_csv(ROOT / "data" / "XAUUSD_M15.csv")
    m["ts"] = pd.to_datetime(m["timestamp"], utc=True)
    m = m.sort_values("ts").reset_index(drop=True)
    roll = m["instrument_id"].ne(m["instrument_id"].shift()) & (m.index > 0)
    f = np.where(roll, m["open"] / m["close"].shift(), 1.0)
    adj = pd.Series(f[::-1]).cumprod()[::-1].shift(-1, fill_value=1.0).to_numpy()  # product of later roll factors
    for c in ("open", "high", "low", "close"):
        m[c] = m[c] * adj
    g = m.set_index("ts").resample("1h", label="left", closed="left")
    h = pd.DataFrame({"open": g["open"].first(), "close": g["close"].last()}).dropna().reset_index()
    ny = h["ts"].dt.tz_convert(NY)
    h["hour"] = ny.dt.hour
    h["tdate"] = (ny.dt.tz_localize(None) + pd.Timedelta(hours=7)).dt.normalize()
    return h


def daily_table(h: pd.DataFrame) -> pd.DataFrame:
    g = h.groupby("tdate")
    d = pd.DataFrame({"close": g["close"].last()})
    bar = lambda hr, col: h[h["hour"] == hr].set_index("tdate")[col]
    d["c09"] = bar(8, "close")                 # close of 08:00-09:00 bar = 09:00 NY
    d["o12"], d["c12"] = bar(12, "open"), bar(12, "close")
    d["o18"], d["c08"] = bar(18, "open"), bar(7, "close")   # session open 18:00 (previous evening) -> 08:00
    d = d.sort_index()
    d["r"] = d["close"].pct_change()
    d["r4"] = d["c12"] / d["o12"] - 1
    d["r5"] = d["c08"] / d["o18"] - 1
    return d


def _w(series_known_through_t: pd.Series) -> pd.Series:
    vol = series_known_through_t.rolling(VOL_LB, min_periods=VOL_LB).std() * np.sqrt(252)
    return (TARGET_VOL / vol).clip(upper=W_CAP)


def signals(d: pd.DataFrame) -> dict[str, pd.Series]:
    p = d["close"]
    return {
        "S1_tsmom12m": np.sign(p / p.shift(252) - 1),
        "S2_tsmom1m": np.sign(p / p.shift(21) - 1),
        "S3_ma200": np.sign(p - p.rolling(200).mean()),
        "S4_intraday_mom": np.sign(d["c09"] / d["close"].shift(1) - 1),
        "S5_asia_drift": pd.Series(1.0, index=d.index),
    }


def strategy_returns(d: pd.DataFrame, sig: dict[str, pd.Series]) -> pd.DataFrame:
    out = {}
    cost_pct = COST_SIDE / d["close"]
    w_daily = _w(d["r"])                         # known at close t, used for day t+1
    for k in ("S1_tsmom12m", "S2_tsmom1m", "S3_ma200"):
        if k not in sig:
            continue
        pos = (sig[k] * w_daily).shift(1)        # decided at close t-1, held over day t
        out[k] = pos * d["r"] - pos.diff().abs() * cost_pct
    if "S4_intraday_mom" in sig:
        w4 = _w(d["r4"]).shift(1)                # vol of previous days only
        pos = sig["S4_intraday_mom"] * w4
        out["S4_intraday_mom"] = pos * d["r4"] - 2 * pos.abs() * cost_pct
    if "S5_asia_drift" in sig:
        w5 = _w(d["r5"]).shift(1)
        pos = sig["S5_asia_drift"] * w5
        out["S5_asia_drift"] = pos * d["r5"] - 2 * pos.abs() * cost_pct
    return pd.DataFrame(out)


def buy_hold(d: pd.DataFrame) -> pd.Series:
    pos = _w(d["r"]).shift(1)
    return pos * d["r"] - pos.diff().abs() * (COST_SIDE / d["close"])


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 20:
        return {"days": len(r)}
    eq = r.cumsum()
    return {"days": int(len(r)), "ann_ret": float(r.mean() * 252), "ann_vol": float(r.std() * np.sqrt(252)),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else np.nan,
            "t_stat": float(r.mean() / r.std() * np.sqrt(len(r))) if r.std() > 0 else np.nan,
            "max_dd": float((eq - eq.cummax()).min())}


def window(x, a, b):
    return x[(x.index >= pd.Timestamp(a)) & (x.index < pd.Timestamp(b))]


def alpha_vs(r: pd.Series, bench: pd.Series, lags: int = 5) -> dict:
    df = pd.concat([r, bench], axis=1).dropna()
    y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    X = np.c_[np.ones(len(x)), x]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    xe = X * e[:, None]
    S = xe.T @ xe
    for L in range(1, lags + 1):
        G = xe[L:].T @ xe[:-L]
        S += (1 - L / (lags + 1)) * (G + G.T)
    XtX_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(XtX_inv @ S @ XtX_inv))
    return {"alpha_ann": float(beta[0] * 252), "beta": float(beta[1]), "t_alpha_nw": float(beta[0] / se[0])}


def combo(rets: pd.DataFrame, names) -> pd.Series:
    return rets[list(names)].mean(axis=1, skipna=False)


def null_pvalue(d, sig, names, obs_sharpe, a, b, rng) -> float:
    n = len(d)
    null = []
    for _ in range(N_PERM):
        s2 = {}
        for k in names:
            if k == "S5_asia_drift":
                s2[k] = pd.Series(np.where(rng.random(n) < 0.5, 1.0, -1.0), index=d.index)
            else:
                s2[k] = pd.Series(np.roll(sig[k].to_numpy(), int(rng.integers(60, n - 60))), index=d.index)
        r = combo(strategy_returns(d, s2), names)
        null.append(metrics(window(r, a, b)).get("sharpe", np.nan))
    null = np.array(null)
    null = null[np.isfinite(null)]
    return float((1 + (null >= obs_sharpe).sum()) / (1 + len(null)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    d = daily_table(load_h1_ratio())
    sig = signals(d)
    rets = strategy_returns(d, sig)
    start = rets.dropna().index[0]          # all five warmed up
    rets, bh = rets[rets.index >= start], buy_hold(d)[lambda s: s.index >= start]
    names_all = list(rets.columns)
    tv = (SPLITS["TRAIN"][0], SPLITS["VALIDATION"][1])

    rows = []
    for k in range(1, 6):
        for names in itertools.combinations(names_all, k):
            r = combo(rets, names)
            row = {"combo": " + ".join(n.split("_")[0] for n in names), "k": k}
            for sp, (a, b) in SPLITS.items():
                row[f"{sp}_sharpe"] = metrics(window(r, a, b)).get("sharpe")
            row["TV_sharpe"] = metrics(window(r, *tv)).get("sharpe")
            row["TV_t_alpha_vs_BH"] = alpha_vs(window(r, *tv), window(bh, *tv))["t_alpha_nw"]
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "ALL_31_COMBINATIONS.csv", index=False)

    per = []
    for k in names_all + ["BUY_HOLD"]:
        r = bh if k == "BUY_HOLD" else rets[k]
        per.append({"strategy": k, **{f"{sp}_{m}": metrics(window(r, a, b)).get(m)
                                       for sp, (a, b) in SPLITS.items() for m in ("sharpe", "ann_ret", "max_dd")}})
    per = pd.DataFrame(per)
    per.to_csv(OUT / "PER_STRATEGY.csv", index=False)

    main_r = combo(rets, names_all)
    res = {"start": str(start.date()), "main_combo": {}}
    for sp, (a, b) in {**SPLITS, "TRAIN+VALIDATION": tv}.items():
        res["main_combo"][sp] = {**metrics(window(main_r, a, b)), **alpha_vs(window(main_r, a, b), window(bh, a, b))}
    obs = res["main_combo"]["TRAIN+VALIDATION"]["sharpe"]
    res["main_combo"]["null_p_TV"] = null_pvalue(d, sig, names_all, obs, *tv, rng)
    m = res["main_combo"]
    res["criteria"] = {
        "sharpe_TRAIN>0": m["TRAIN"]["sharpe"] > 0, "sharpe_VALIDATION>0": m["VALIDATION"]["sharpe"] > 0,
        "null_p<0.05": m["null_p_TV"] < 0.05, "t_alpha_vs_BH>2": m["TRAIN+VALIDATION"]["t_alpha_nw"] > 2,
        "sharpe_TEST>0 (contaminated)": m["TEST"]["sharpe"] > 0}
    (OUT / "RESULT.json").write_text(json.dumps(res, indent=2, default=str))
    pd.DataFrame({"combo_5": main_r.cumsum(), "buy_hold": bh.cumsum()}).to_csv(OUT / "equity.csv")
    print(json.dumps(res, indent=1, default=str))
    print(per.round(3).to_string())
    print(table.sort_values("TV_sharpe", ascending=False).round(2).to_string())


if __name__ == "__main__":
    main()
