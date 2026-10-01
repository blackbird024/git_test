"""Building blocks (all causal: value at bar i uses bars <= i, bar i is closed) and random strategies.

A strategy = direction + AND of 1-3 entry conditions + exit (ATR stop, ATR target or none, max bars).
Entry at the OPEN of bar i+1 after the conditions are true at the close of bar i.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# condition family -> parameter grid (ordered lists so "neighbour" = adjacent grid value)
GRID: dict[str, dict[str, list]] = {
    "above_sma": {"n": [20, 50, 100, 200]},
    "below_sma": {"n": [20, 50, 100, 200]},
    "sma_cross_up": {"pair": [(10, 50), (20, 100), (50, 200)]},
    "sma_cross_dn": {"pair": [(10, 50), (20, 100), (50, 200)]},
    "rsi_below": {"n": [2, 7, 14], "lvl": [10, 20, 30]},
    "rsi_above": {"n": [2, 7, 14], "lvl": [70, 80, 90]},
    "breakout_up": {"n": [10, 20, 50]},
    "breakout_dn": {"n": [10, 20, 50]},
    "boll_below": {"n": [20, 50], "k": [1.5, 2.0, 2.5]},
    "boll_above": {"n": [20, 50], "k": [1.5, 2.0, 2.5]},
    "down_closes": {"m": [2, 3, 4]},
    "up_closes": {"m": [2, 3, 4]},
    "engulf_bull": {},
    "engulf_bear": {},
    "inside_bar": {},
    "hour_window": {"h": list(range(24)), "w": [1, 2, 3, 4]},
    "weekday": {"d": [0, 1, 2, 3, 4]},
    "atr_ratio_above": {"r": [0.8, 1.0, 1.2]},
    "atr_ratio_below": {"r": [0.8, 1.0, 1.2]},
    "roc_pos": {"n": [5, 10, 20]},
    "roc_neg": {"n": [5, 10, 20]},
    "volume_spike": {"k": [1.5, 2.0]},
    "above_prev_day_high": {},
    "below_prev_day_low": {},
}
EXIT_GRID = {"sl": [1.0, 1.5, 2.0, 3.0], "tp": [1.0, 1.5, 2.0, 3.0, 4.0, None], "bars": [4, 8, 16, 24, 48]}


def _rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn)


class Features:
    """Lazily computed, cached boolean arrays per (family, params)."""

    def __init__(self, h: pd.DataFrame):
        self.h = h
        self.o, self.hi, self.lo, self.c, self.v = (h[k] for k in ("open", "high", "low", "close", "volume"))
        tr = pd.concat([self.hi - self.lo, (self.hi - self.c.shift()).abs(), (self.lo - self.c.shift()).abs()], axis=1).max(axis=1)
        self.atr14 = tr.rolling(14).mean()
        self.atr100 = tr.rolling(100).mean()
        day = h.groupby("tdate").agg(dh=("high", "max"), dl=("low", "min"))
        prev = day.shift(1)  # previous session's range, known from the first bar of the session
        self.prev_hi = h["tdate"].map(prev["dh"])
        self.prev_lo = h["tdate"].map(prev["dl"])
        self.cache: dict = {}

    def get(self, fam: str, p: dict) -> np.ndarray:
        key = (fam, tuple(sorted(p.items())))
        if key not in self.cache:
            self.cache[key] = np.asarray(self._compute(fam, p).fillna(False), dtype=bool)
        return self.cache[key]

    def _compute(self, fam, p):
        c, o, hi, lo, v, h = self.c, self.o, self.hi, self.lo, self.v, self.h
        if fam == "above_sma":
            return c > c.rolling(p["n"]).mean()
        if fam == "below_sma":
            return c < c.rolling(p["n"]).mean()
        if fam in ("sma_cross_up", "sma_cross_dn"):
            f, s = p["pair"]
            d = c.rolling(f).mean() - c.rolling(s).mean()
            return (d > 0) & (d.shift() <= 0) if fam == "sma_cross_up" else (d < 0) & (d.shift() >= 0)
        if fam == "rsi_below":
            return _rsi(c, p["n"]) < p["lvl"]
        if fam == "rsi_above":
            return _rsi(c, p["n"]) > p["lvl"]
        if fam == "breakout_up":
            return c > hi.shift(1).rolling(p["n"]).max()
        if fam == "breakout_dn":
            return c < lo.shift(1).rolling(p["n"]).min()
        if fam in ("boll_below", "boll_above"):
            m, s = c.rolling(p["n"]).mean(), c.rolling(p["n"]).std()
            return c < m - p["k"] * s if fam == "boll_below" else c > m + p["k"] * s
        if fam in ("down_closes", "up_closes"):
            d = c.diff()
            x = (d < 0) if fam == "down_closes" else (d > 0)
            return x.astype(float).rolling(p["m"]).sum() == p["m"]
        if fam == "engulf_bull":
            return (c.shift() < o.shift()) & (c > o) & (o <= c.shift()) & (c >= o.shift())
        if fam == "engulf_bear":
            return (c.shift() > o.shift()) & (c < o) & (o >= c.shift()) & (c <= o.shift())
        if fam == "inside_bar":
            return (hi < hi.shift()) & (lo > lo.shift())
        if fam == "hour_window":
            hrs = [(p["h"] + k) % 24 for k in range(p["w"])]
            return h["hour_ny"].isin(hrs)
        if fam == "weekday":
            return h["dow"] == p["d"]
        if fam == "atr_ratio_above":
            return self.atr14 / self.atr100 > p["r"]
        if fam == "atr_ratio_below":
            return self.atr14 / self.atr100 < p["r"]
        if fam == "roc_pos":
            return c / c.shift(p["n"]) - 1 > 0
        if fam == "roc_neg":
            return c / c.shift(p["n"]) - 1 < 0
        if fam == "volume_spike":
            return v / v.shift(1).rolling(20).mean() > p["k"]
        if fam == "above_prev_day_high":
            return c > self.prev_hi
        if fam == "below_prev_day_low":
            return c < self.prev_lo
        raise ValueError(fam)


@dataclass(frozen=True)
class Strategy:
    direction: str                     # 'long' | 'short'
    conds: tuple                       # ((family, frozenset(params.items())), ...)
    sl: float
    tp: float | None
    bars: int
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    def key(self) -> str:
        cs = " & ".join(f"{f}({','.join(f'{k}={v}' for k, v in sorted(p))})" for f, p in self.conds)
        return f"{self.direction.upper()} [{cs}] SL={self.sl}ATR TP={self.tp}ATR max={self.bars}h"


def _cond(fam, params: dict):
    return (fam, frozenset(params.items()))


def random_strategy(rng: np.random.Generator) -> Strategy:
    fams = list(GRID)
    k = int(rng.integers(1, 4))
    chosen = rng.choice(len(fams), size=k, replace=False)
    conds = []
    for i in sorted(chosen):
        fam = fams[i]
        conds.append(_cond(fam, {name: vals[int(rng.integers(len(vals)))] for name, vals in GRID[fam].items()}))
    return Strategy(direction="long" if rng.random() < 0.5 else "short", conds=tuple(conds),
                    sl=EXIT_GRID["sl"][int(rng.integers(4))], tp=EXIT_GRID["tp"][int(rng.integers(6))],
                    bars=EXIT_GRID["bars"][int(rng.integers(5))])


def neighbours(s: Strategy) -> list[Strategy]:
    """Every strategy one grid step away in exactly one numeric parameter (entry or exit)."""
    out = []
    for ci, (fam, params) in enumerate(s.conds):
        p = dict(params)
        for name, vals in GRID[fam].items():
            j = vals.index(p[name])
            for jj in (j - 1, j + 1):
                if 0 <= jj < len(vals) and not (fam == "hour_window" and name == "h"):
                    q = dict(p); q[name] = vals[jj]
                    conds = list(s.conds); conds[ci] = _cond(fam, q)
                    out.append(Strategy(s.direction, tuple(conds), s.sl, s.tp, s.bars))
            if fam == "hour_window" and name == "h":  # cyclic
                for dh in (-1, 1):
                    q = dict(p); q["h"] = (p["h"] + dh) % 24
                    conds = list(s.conds); conds[ci] = _cond(fam, q)
                    out.append(Strategy(s.direction, tuple(conds), s.sl, s.tp, s.bars))
    for name in ("sl", "tp", "bars"):
        vals = EXIT_GRID[name]
        j = vals.index(getattr(s, name))
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(vals):
                kw = {"sl": s.sl, "tp": s.tp, "bars": s.bars, name: vals[jj]}
                out.append(Strategy(s.direction, s.conds, **kw))
    return out


def search_space_size() -> int:
    per_fam = {f: max(1, int(np.prod([len(v) for v in g.values()]))) for f, g in GRID.items()}
    fams = list(per_fam)
    n_entries = sum(np.prod([per_fam[f] for f in combo]) for k in (1, 2, 3) for combo in itertools.combinations(fams, k))
    return int(n_entries * 2 * 4 * 6 * 5)
