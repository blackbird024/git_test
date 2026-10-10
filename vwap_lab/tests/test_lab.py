"""Pruebas de indicadores, cruces, pendiente, señales, entradas, stops, salidas, tamaño y ausencia de lookahead."""
from datetime import time

import numpy as np
import pandas as pd
import pytest

from vwap_lab.src.backtest.engine import run_session
from vwap_lab.src.data import loader
from vwap_lab.src.indicators import core
from vwap_lab.src.strategies.signals import _cross, signals

P = dict(stop_buffer_ticks=1, atr_stop_mult=1.0, retest_bars=3, retest_tolerance_ticks=2, retest_max_depth_atr=0.5,
         ema50_slope_bars=6, min_risk_to_cost=3.0, max_trades_per_session=2)
INST = dict(symbol="MNQ", tick_size=0.25, tick_value=0.5, point_value=2.0)
COST0 = dict(commission_per_side=0.0, slippage_ticks_per_side=0, limit_fill_ticks_through=1)
RISK = dict(initial_capital=50000, risk_pct=0.0025, compounding=True)


def test_vwap_formula_and_reset():
    h, l, c, v = np.array([11., 13]), np.array([9., 11]), np.array([10., 12]), np.array([1., 3])
    vw = core.session_vwap(h, l, c, v)
    assert vw[0] == 10 and vw[1] == pytest.approx((10 * 1 + 12 * 3) / 4)
    assert core.session_vwap(h[1:], l[1:], c[1:], v[1:])[0] == 12          # otra sesión: empieza de cero


def test_ema_and_atr_have_no_lookahead():
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(size=300))
    c2 = c.copy(); c2[200:] += 50
    assert np.allclose(core.ema(c, 9)[:200], core.ema(c2, 9)[:200])
    h, l = c + 1, c - 1
    assert np.allclose(core.atr(h, l, c)[:200], core.atr(c2 + 1, c2 - 1, c2)[:200])
    assert core.ema(c, 9)[5] == pytest.approx(pd.Series(c).ewm(span=9, adjust=False).mean()[5])


def test_slope_definition():
    vw = np.arange(10, dtype=float)
    at = np.full(10, 2.0)
    s = core.vwap_slope(vw, at, 6)
    assert np.isnan(s[:6]).all() and s[6] == pytest.approx(6 / 2)


def test_cross_requires_change_of_side():
    x = np.array([1, 2, 3, 3, 3.0]); y = np.array([2, 2, 2, 2, 2.0])
    up, dn = _cross(x, y)
    assert list(up) == [False, False, True, False, False] and not dn.any()


def _arr(n=20, base=100.0):
    a = {k: np.full(n, base) for k in ("o", "h", "l", "c", "ema9", "ema20", "ema21", "ema50", "vwap")}
    a["h"] = a["h"] + 0.5; a["l"] = a["l"] - 0.5
    a["slope"] = np.full(n, 0.2); a["atr"] = np.full(n, 2.0); a["ema50_delta"] = np.zeros(n)
    return a


def test_strategy_A_long_and_filter():
    a = _arr()
    a["ema9"][5:] = 101; a["c"][5:] = 101.5                       # EMA9 cruza el VWAP en la vela 5
    side, _ = signals(a, "A", 0.10, P, 0.25)
    assert side[5] == 1 and side.sum() == 1
    a["slope"][:] = 0.05
    assert signals(a, "A", 0.10, P, 0.25)[0].sum() == 0          # VWAP plano: filtrada
    assert signals(a, "A", None, P, 0.25)[0][5] == 1              # sin filtro


def test_strategy_E_retest_window():
    a = _arr()
    a["ema9"][5:] = 101; a["ema21"][:] = 100.5; a["c"][5:] = 102; a["l"][5:] = 101.5
    a["l"][8] = 100.75; a["c"][8] = 101.0                           # retesteo en la 3.ª vela tras el cruce
    side, ref = signals(a, "E", 0.10, P, 0.25)
    assert side[8] == 1 and ref[8] == 8
    a["l"][8] = 101.5; a["l"][9] = 100.75                            # en la 4.ª: caduca
    assert signals(a, "E", 0.10, P, 0.25)[0].sum() == 0


class _S:
    def __init__(self, n=20, flat_pos=None, entry_end=time(15, 30)):
        self.name, self.date = "newyork", pd.Timestamp("2024-03-05")
        self.start = pd.date_range("2024-03-05 09:30", periods=n, freq="5min", tz="America/New_York")
        self.flat_pos = n - 1 if flat_pos is None else flat_pos
        self.entry_end = entry_end


def _run(a, side, cost=COST0, n_tr=2, target=2.0, **kw):
    s = _S(len(a["c"]), **kw)
    ref = np.arange(len(side))
    return run_session(s, a, side, ref, INST, cost, P, RISK, 50000.0, "A", 0.1, target, max_trades=n_tr)[0]


def test_entry_next_open_stop_target_and_size():
    a = _arr(); side = np.zeros(20, int); side[5] = 1
    a["l"][5] = 98.0                                                 # stop = 98 − 1 tick
    a["o"][6] = 100.0
    a["h"][9] = 103.75 + 0.25                                        # objetivo 2R = 100 + 2·2.25 = 104.5 → no
    a["h"][10] = 104.75                                              # lo supera 1 tick → objetivo
    tr = _run(a, side)
    t = tr[0]
    assert t.entry == 100.0 and t.stop == 97.75 and t.target == 104.5 and t.exit_reason == "objetivo"
    assert t.contracts == int(125 // (2.25 * 2))


def test_stop_first_same_bar_and_gap():
    a = _arr(); side = np.zeros(20, int); side[5] = 1; a["l"][5] = 98.0
    a["h"][7] = 110; a["l"][7] = 90
    t = _run(a, side)[0]
    assert t.exit_reason == "stop" and t.ambiguous
    a = _arr(); side = np.zeros(20, int); side[5] = 1; a["l"][5] = 98.0
    a["o"][8] = 95; a["l"][8] = 94
    assert _run(a, side)[0].exit_reason == "stop_hueco" and _run(a, side)[0].exit == 95


def test_flat_exit_and_entry_deadline():
    a = _arr(); side = np.zeros(20, int); side[5] = 1; a["l"][5] = 98.0
    t = _run(a, side, flat_pos=12)[0]
    assert t.exit_reason == "cierre_sesion" and t.exit_time.startswith("2024-03-05 10:30")
    assert _run(a, side, entry_end=time(9, 55)) == []                # la vela de entrada (10:00) es tardía


def test_max_trades_and_sequencing():
    a = _arr(); side = np.zeros(20, int); side[[3, 4, 8, 12]] = 1
    a["l"][[3, 8, 12]] = 98.0
    a["l"][6] = 90                                                    # stop de la 1.ª en la vela 6
    a["l"][10] = 90                                                   # stop de la 2.ª
    tr = _run(a, side)
    assert len(tr) == 2 and tr[0].signal_time.startswith("2024-03-05 09:50") and tr[1].signal_time.startswith("2024-03-05 10:15")


def test_skip_small_stop_and_oversized_risk():
    cost = dict(commission_per_side=0.62, slippage_ticks_per_side=1, limit_fill_ticks_through=1)
    a = _arr(); side = np.zeros(20, int); side[5] = 1; a["l"][5] = 99.75          # riesgo 0,5 pt = 1 $ < 3 × 2,24 $
    assert _run(a, side, cost=cost) == []
    a["l"][5] = 20.0                                                                 # riesgo 80 pt = 160 $ > 125 $
    assert _run(a, side, cost=cost) == []


def test_london_sessions_follow_uk_clock(tmp_path):
    idx = pd.date_range("2024-03-28 00:00", "2024-04-03 23:55", freq="5min", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    df = pd.DataFrame({"open": 100.0, "high": 100.25, "low": 99.75, "close": 100.0, "volume": 10.0, "contract": "X"}, index=idx)
    s = loader.sessions(df, dict(timezone="Europe/London", start="08:00", entry_end="10:45", flat="11:00", name="london"),
                        dict(min_bar_coverage=0.9, exclude_first_session_after_roll=True))
    by = {str(x.date.date()): x for x in s}
    assert by["2024-03-28"].start[0].tz_convert("UTC").hour == 8 and by["2024-04-02"].start[0].tz_convert("UTC").hour == 7
    assert by["2024-04-02"].flat_pos == len(by["2024-04-02"].idx) - 1
