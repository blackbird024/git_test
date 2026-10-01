"""Vectorised H1 backtest, one position at a time per strategy.

- Signal at the close of bar i -> entry at OPEN of bar i+1.
- Stop = sl x ATR14(i) from entry, target = tp x ATR14(i) (or none), time exit after `bars` bars.
- Same bar touches stop and target -> stop (conservative). Gap through stop -> fill at open.
- Holding is cut at the close of the bar before any contract roll.
- Cost per trade (price units/oz): spread + commission + 2 x slippage, as in the CRT study.
Returns per-trade R (net), where 1R = stop distance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .rules import Features, Strategy

COST = 0.20 + 0.07 + 2 * 0.05  # same pre-registered placeholders as CONFIG.json (USD/oz per round trip)


class Engine:
    def __init__(self, h: pd.DataFrame, feats: Features | None = None, cost: float = COST):
        self.h = h
        self.f = feats or Features(h)
        self.o, self.hi, self.lo, self.c = (h[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.atr = self.f.atr14.to_numpy(float)
        self.ts = h["ts"].to_numpy()
        self.n = len(h)
        self.cost = cost
        roll = h["roll_before"].to_numpy(bool)
        # next roll bar index at or after j (n if none)
        nxt = np.full(self.n + 1, self.n)
        for j in range(self.n - 1, -1, -1):
            nxt[j] = j if roll[j] else nxt[j + 1]
        self.next_roll = nxt

    def signal(self, s: Strategy) -> np.ndarray:
        m = np.ones(self.n, bool)
        for fam, p in s.conds:
            m &= self.f.get(fam, dict(p))
        return m

    def run(self, s: Strategy, delay: int = 0, cost_mult: float = 1.0) -> pd.DataFrame:
        sig = np.flatnonzero(self.signal(s))
        ent = sig + 1 + delay
        ok = ent < self.n
        sig, ent = sig[ok], ent[ok]
        a = self.atr[sig]
        ok = np.isfinite(a) & (a > 0) & (self.next_roll[sig + 1] > ent)  # no roll between signal and entry
        sig, ent, a = sig[ok], ent[ok], a[ok]
        if len(ent) == 0:
            return _empty()
        T = s.bars
        last = np.minimum(np.minimum(ent + T - 1, self.next_roll[ent + 1] - 1), self.n - 1)
        last = np.maximum(last, ent)
        idx = ent[:, None] + np.arange(T)[None, :]
        valid = idx <= last[:, None]
        idx = np.minimum(idx, self.n - 1)
        d = 1.0 if s.direction == "long" else -1.0
        entry = self.o[ent]
        risk = s.sl * a
        stop = entry - d * risk
        hi, lo, op = self.hi[idx], self.lo[idx], self.o[idx]
        if d > 0:
            hit_sl = (lo <= stop[:, None]) & valid
            hit_tp = (hi >= (entry + s.tp * a)[:, None]) & valid if s.tp else np.zeros_like(hit_sl)
        else:
            hit_sl = (hi >= stop[:, None]) & valid
            hit_tp = (lo <= (entry - s.tp * a)[:, None]) & valid if s.tp else np.zeros_like(hit_sl)
        big = T + 1
        k_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), big)
        k_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), big)
        k_time = last - ent
        rows = np.arange(len(ent))
        stop_first = k_sl <= k_tp
        k = np.where((k_sl < big) & stop_first, k_sl, np.where(k_tp < big, k_tp, k_time))
        sl_fill = np.where(d > 0, np.minimum(op[rows, np.minimum(k_sl, T - 1)], stop),
                           np.maximum(op[rows, np.minimum(k_sl, T - 1)], stop))
        sl_fill = np.where(k_sl == 0, stop, sl_fill)  # entry bar opens at entry, never beyond stop
        exit_px = np.where((k_sl < big) & stop_first, sl_fill,
                           np.where(k_tp < big, entry + d * (s.tp or 0) * a, self.c[ent + k_time]))
        exit_i = ent + k
        # one position at a time: greedy in time order
        keep = np.zeros(len(ent), bool)
        busy = -1
        for j in range(len(ent)):
            if ent[j] > busy:
                keep[j] = True
                busy = exit_i[j]
        pnl = d * (exit_px - entry) - cost_mult * self.cost
        r = pnl / risk
        return pd.DataFrame({"entry_i": ent[keep], "exit_i": exit_i[keep], "entry_time": self.ts[ent[keep]],
                             "R": r[keep], "gross_R": (d * (exit_px - entry) / risk)[keep]})


def _empty():
    return pd.DataFrame({"entry_i": [], "exit_i": [], "entry_time": [], "R": [], "gross_R": []})


def stats(t: pd.DataFrame) -> dict:
    n = len(t)
    if n == 0:
        return {"n": 0, "exp": np.nan, "pf": np.nan, "tot": 0.0, "dd": 0.0, "sr": np.nan, "pos_years": np.nan}
    r = t["R"].to_numpy(float)
    eq = np.cumsum(r)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    neg = -r[r < 0].sum()
    yrs = pd.Series(r, index=pd.to_datetime(t["entry_time"]).dt.year).groupby(level=0).sum()
    sd = r.std(ddof=1) if n > 1 else np.nan
    return {"n": n, "exp": float(r.mean()), "pf": float(r[r > 0].sum() / neg) if neg > 0 else np.inf,
            "tot": float(r.sum()), "dd": dd, "sr": float(r.mean() / sd) if sd and sd > 0 else np.nan,
            "pos_years": float((yrs > 0).mean()), "gross_exp": float(t["gross_R"].mean())}
