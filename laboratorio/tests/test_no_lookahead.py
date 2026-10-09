"""Pruebas contra el uso de información futura."""
import numpy as np
import pandas as pd

from data.loaders import Session
from execution_costs.costs import FutCost
from strategies.features import daily_context
from strategies.noise import noise_trades
from strategies.trend import trend

C0 = FutCost(point_value=2.0, tick=0.25, fixed_per_side=0.0, slip_ticks=0)


def test_daily_context_uses_previous_day_only():
    idx = pd.date_range("2024-01-01", periods=300, freq="B")
    close = pd.Series(np.arange(300, dtype=float) + 100, index=idx)
    d = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close})
    ctx = daily_context(d)
    assert ctx[idx[10]]["prev_close"] == close.iloc[9]
    # cambiar el futuro no cambia el contexto del pasado
    d2 = d.copy(); d2.iloc[200:, :] *= 3
    a, b = daily_context(d2)[idx[150]], ctx[idx[150]]
    assert np.allclose(list(a.values()), list(b.values()), equal_nan=True)


def _session(date, base, drift):
    m = np.full((390, 5), np.nan)
    p = base + drift * np.arange(390) / 390
    m[:, 0] = p; m[:, 1] = p + 0.25; m[:, 2] = p - 0.25; m[:, 3] = p; m[:, 4] = 1
    return Session(pd.Timestamp(date), m, 390, 1, False)


def test_noise_signals_do_not_depend_on_future_sessions():
    days = pd.bdate_range("2024-01-01", periods=40)
    S = [_session(d, 100 + i, (5 if i % 3 else -4)) for i, d in enumerate(days)]
    a = [f for f in noise_trades(S, C0) if f.date <= days[30]]
    S2 = S[:31] + [_session(d, 500, 50) for d in days[31:]]          # futuro distinto
    b = [f for f in noise_trades(S2, C0) if f.date <= days[30]]
    assert [(f.date, f.side, f.entry, f.exit) for f in a] == [(f.date, f.side, f.entry, f.exit) for f in b]


def test_trend_needs_context_and_respects_direction():
    s = _session("2024-03-01", 100, 10)          # día alcista
    ctx = {s.date: dict(prev_close=99, ema50=90, ema200=80, atr14=2, atr_pct=0.02, vol_rank=0.5)}
    o = trend(s, ctx)
    assert o is None or o.side == 1
    assert trend(s, {}) is None
