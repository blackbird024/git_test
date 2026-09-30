"""Tests designed to show the BASE result is NOT specific to the hypothesised mechanism.

Each null keeps everything except one link and asks how often chance matches the observed
mean R. p = (1 + #null >= observed) / (1 + n_perm). All evaluated on the same span as the observed
trades (TRAIN+VALIDATION unless TEST was explicitly unlocked).

- random_direction : same entries / stop distances, direction assigned by coin flip.
- time_randomization: same days, same KZ, same direction and stop distance; entry bar drawn
                      uniformly among the KZ bars of that setup.
- random_entry     : same trade count, random setups & KZ bars, random direction, stop distance
                      drawn from the observed distribution (no signal at all).
- volume_permutation: volumes shuffled among bars of the SAME New-York time-of-day inside the span
                      (keeps intraday seasonality), full detector re-run.
- randomized_sweep : every reference 4H high/low replaced by close + the (high-close, close-low)
                      offsets of a random other complete 4H bucket, full detector re-run.
- ablations (single runs, descriptive): no sweep requirement; no volume requirement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import add_bar_features
from .execution import Market, build_trades, combine_groups, cost_price, simulate
from .signals import detect_all


def _sim_R(m: Market, ei: int, direction: str, risk: float, target_R: float, cost: float) -> float:
    if ei >= m.n or risk <= 0:
        return np.nan
    last_i = int(m.last_idx[ei])
    if ei > last_i:
        return np.nan
    entry = m.o[ei]
    sgn = 1.0 if direction == "long" else -1.0
    sl = entry - sgn * risk
    tp = entry + sgn * target_R * risk
    sim = simulate(m, ei, direction, entry, sl, tp, last_i)
    if not m.same_contract(ei - 1, sim["exit_i"]):
        return np.nan
    return (sgn * (sim["exit_price"] - entry) - cost) / risk


def _p(null: np.ndarray, obs: float) -> dict:
    null = null[np.isfinite(null)]
    if len(null) == 0 or not np.isfinite(obs):
        return {"observed_mean_R": obs, "n_null": 0}
    return {"observed_mean_R": float(obs), "null_mean": float(null.mean()), "null_p95": float(np.percentile(null, 95)),
            "p_value": float((1 + (null >= obs).sum()) / (1 + len(null))), "n_null": int(len(null))}


def kz_candidates(df: pd.DataFrame, setups: pd.DataFrame) -> dict[str, np.ndarray]:
    """Row indices of bars that can be a confirmation bar inside each setup's KZ window."""
    wall = df["ny"].dt.tz_localize(None).to_numpy()
    out = {}
    for s in setups.itertuples(index=False):
        a = np.searchsorted(wall, np.datetime64(s.kz_start), "left")
        b = np.searchsorted(wall, np.datetime64(s.kz_end) - np.timedelta64(15, "m"), "right")
        out[s.setup_id] = np.arange(a, b)
    return out


def run_all(trades: pd.DataFrame, df: pd.DataFrame, h4: pd.DataFrame, setups: pd.DataFrame, cfg: dict,
            span: tuple, group: str, rng: np.random.Generator) -> dict:
    fz = cfg["falsification"]
    n_perm, n_vperm = fz["n_permutations"], fz["n_volume_permutations"]
    m = Market(df, cfg)
    cost = cost_price(cfg)
    tp_key = cfg["execution"]["base_tp"]
    target_R = cfg["execution"]["take_profits"][tp_key]["value"]
    res = {}
    if len(trades) < 5:
        return {"status": "too few trades for falsification", "trades": int(len(trades))}
    obs = float(trades["R"].mean())
    ei = (trades["conf_i"].to_numpy(int) + 1)
    risk = trades["stop_distance"].to_numpy(float)
    dirs = trades["direction"].to_numpy()

    # 1) random direction
    rl = np.array([_sim_R(m, e, "long", r, target_R, cost) for e, r in zip(ei, risk)])
    rs = np.array([_sim_R(m, e, "short", r, target_R, cost) for e, r in zip(ei, risk)])
    flips = rng.random((n_perm, len(ei))) < 0.5
    res["random_direction"] = _p(np.nanmean(np.where(flips, rl, rs), axis=1), obs)

    # 2) time randomization within the same KZ window
    cand = kz_candidates(df, setups)
    per_trade = []
    for sid, d, r in zip(trades["setup_id"], dirs, risk):
        c = cand.get(sid, np.array([], int))
        per_trade.append(np.array([_sim_R(m, j + 1, d, r, target_R, cost) for j in c]))
    null = np.empty(n_perm)
    for k in range(n_perm):
        vals = [pt[rng.integers(len(pt))] for pt in per_trade if len(pt)]
        null[k] = np.nanmean(vals) if vals else np.nan
    res["time_randomization"] = _p(null, obs)

    # 3) random entry (signal removed)
    grp_kz = {"LONDON": ["london"], "NY": ["ny"]}.get(group, ["london", "ny"])
    wall_first = df["ts"].iloc[0]
    pool = []
    for s in setups.itertuples(index=False):
        if s.kz not in grp_kz or not s.ref_exists:
            continue
        c = cand.get(s.setup_id, np.array([], int))
        if len(c) and span[0] <= df["ts"].iloc[c[0]] < span[1] and df["ts"].iloc[c[0]] >= wall_first:
            pool.append(c)
    if pool:
        null = np.empty(n_perm)
        for k in range(n_perm):
            picks = rng.integers(len(pool), size=len(ei))
            vals = []
            for p in picks:
                j = pool[p][rng.integers(len(pool[p]))]
                vals.append(_sim_R(m, j + 1, "long" if rng.random() < 0.5 else "short",
                                   risk[rng.integers(len(risk))], target_R, cost))
            null[k] = np.nanmean(vals)
        res["random_entry"] = _p(null, obs)

    # 4) volume permutation (same time-of-day, inside span only)
    in_span = ((df["ts"] >= span[0]) & (df["ts"] < span[1])).to_numpy()
    tod = (df["ny"].dt.hour * 60 + df["ny"].dt.minute).to_numpy()
    vol = df["volume"].to_numpy(float)
    slots = [np.where(in_span & (tod == t))[0] for t in np.unique(tod[in_span])]
    null = []
    for _ in range(n_vperm):
        v2 = vol.copy()
        for idx in slots:
            v2[idx] = vol[rng.permutation(idx)]
        d2 = add_bar_features(df.assign(volume=v2), cfg)
        null.append(_group_mean(d2, h4, cfg, span, group, cfg["volume"]["base"]))
    res["volume_permutation"] = _p(np.array(null), obs)

    # 5) randomized sweep levels
    comp = h4[h4["complete"]]
    up = (comp["high"] - comp["close"]).to_numpy()
    dn = (comp["close"] - comp["low"]).to_numpy()
    null = []
    for _ in range(n_vperm):
        k = rng.integers(len(up), size=len(h4))
        h4r = h4.copy()
        h4r["high"] = h4["close"].to_numpy() + np.maximum(up[k], 0)
        h4r["low"] = h4["close"].to_numpy() - np.maximum(dn[k], 0)
        null.append(_group_mean(df, h4r, cfg, span, group, cfg["volume"]["base"]))
    res["randomized_sweep"] = _p(np.array(null), obs)

    # 6) ablations
    res["ablation_no_sweep_mean_R"] = _group_mean(df, h4, cfg, span, group, cfg["volume"]["base"], require_sweep=False,
                                                  with_n=True)
    res["ablation_no_volume_mean_R"] = _group_mean(df, h4, cfg, span, group, {"type": "none"}, with_n=True)
    res["observed_mean_R"] = obs
    return res


def _group_mean(df, h4, cfg, span, group, variant, require_sweep=True, with_n=False):
    sig, _, _, _ = detect_all(df, h4, cfg, variant, require_sweep=require_sweep)
    if len(sig) == 0:
        return {"mean_R": np.nan, "trades": 0} if with_n else np.nan
    sig = sig[(sig["signal_time"] >= span[0]) & (sig["signal_time"] < span[1])]
    t, _ = build_trades(sig, Market(df, cfg), cfg, cfg["execution"]["base_tp"])
    t = combine_groups(t)[group] if len(t) else t
    mean = float(t["R"].mean()) if len(t) else np.nan
    return {"mean_R": mean, "trades": int(len(t))} if with_n else mean
