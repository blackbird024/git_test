"""Generator tests on SYNTHETIC H1 bars (test-only data)."""
import numpy as np
import pandas as pd
import pytest

from strategy_gen.backtest import Engine
from strategy_gen.rules import GRID, Features, Strategy, _cond, neighbours, random_strategy


def synth_h1(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2015-01-05", periods=n, freq="1h", tz="UTC")
    c = 1500 + np.cumsum(rng.normal(0, 2, n))
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) + np.abs(rng.normal(0, 1, n))
    lo = np.minimum(o, c) - np.abs(rng.normal(0, 1, n))
    h = pd.DataFrame({"ts": ts, "open": o, "high": hi, "low": lo, "close": c,
                      "volume": rng.integers(100, 1000, n).astype(float), "roll_before": False})
    h["ny"] = h["ts"].dt.tz_convert("America/New_York")
    h["hour_ny"], h["dow"] = h["ny"].dt.hour, h["ny"].dt.dayofweek
    h["tdate"] = (h["ny"].dt.tz_localize(None) + pd.Timedelta(hours=7)).dt.normalize()
    return h


def first_params(fam):
    return {k: v[len(v) // 2] for k, v in GRID[fam].items()}


@pytest.mark.parametrize("fam", list(GRID))
def test_every_condition_is_causal(fam):
    h = synth_h1()
    full = Features(h).get(fam, first_params(fam))
    cut = 2000
    part = Features(h.iloc[:cut].reset_index(drop=True)).get(fam, first_params(fam))
    assert np.array_equal(full[:cut - 30], part[:cut - 30])  # prev-day mapping may differ only at the cut session


def _engine(o, hi, lo, c):
    h = synth_h1(len(o))
    h["open"], h["high"], h["low"], h["close"] = o, hi, lo, c
    e = Engine(h)
    e.atr = np.ones(len(o))  # ATR = 1 for hand calculation
    return e


def test_stop_first_when_both_hit_same_bar():
    o = np.array([100, 100, 100, 100.0]); hi = np.array([100, 100, 103, 100.0]); lo = np.array([100, 100, 97, 100.0])
    e = _engine(o, hi, lo, o.copy())
    e.f.cache[("weekday", (("d", 9),))] = np.array([True, False, False, False])
    s = Strategy("long", (_cond("weekday", {"d": 9}),), sl=2.0, tp=2.0, bars=4)
    t = e.run(s, cost_mult=0)
    assert t["R"].iloc[0] == pytest.approx(-1.0)


def test_entry_is_next_open_and_time_exit():
    o = np.array([100, 101, 102, 103, 104.0]); c = o + 0.5
    e = _engine(o, o + 0.6, o - 0.1, c)
    e.f.cache[("weekday", (("d", 9),))] = np.array([True, False, False, False, False])
    s = Strategy("long", (_cond("weekday", {"d": 9}),), sl=3.0, tp=None, bars=2)
    t = e.run(s, cost_mult=0)
    assert t["entry_i"].iloc[0] == 1 and t["exit_i"].iloc[0] == 2
    assert t["R"].iloc[0] == pytest.approx((c[2] - o[1]) / 3.0)


def test_neighbours_change_one_parameter():
    rng = np.random.default_rng(5)
    s = random_strategy(rng)
    for nb in neighbours(s):
        diff = (nb.sl != s.sl) + (nb.tp != s.tp) + (nb.bars != s.bars) + sum(a != b for a, b in zip(nb.conds, s.conds))
        assert diff == 1
