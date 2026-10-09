import numpy as np
import pandas as pd

from backtests.swing import SwingCost, simulate
from strategies.swing import breakout20

C0 = SwingCost(pct_side=0.0, fixed=0.0, capital=1000)


def frame(rows):
    d = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    d.index = pd.bdate_range("2024-01-01", periods=len(d))
    return d


def sig(d, entry_days, exit_days=(), stop=np.nan, md=None):
    s = pd.DataFrame({"entry": False, "exit": False, "stop_dist": stop, "max_days": md}, index=d.index)
    s.iloc[list(entry_days), 0] = True
    if exit_days:
        s.iloc[list(exit_days), 1] = True
    return s


def test_next_open_entry_and_exit():
    d = frame([(10, 10, 10, 10), (11, 12, 11, 12), (12, 13, 12, 13), (14, 14, 14, 14)])
    t = simulate(d, sig(d, [0], [1]), C0, "next_open")
    assert len(t) == 1 and t.px_entrada[0] == 11 and t.px_salida[0] == 12 and t.motivo[0] == "regla"


def test_close_mode_uses_close():
    d = frame([(10, 10, 10, 10), (11, 12, 11, 12), (12, 13, 12, 13)])
    t = simulate(d, sig(d, [0], [1]), C0, "close")
    assert t.px_entrada[0] == 10 and t.px_salida[0] == 12


def test_gap_below_stop_exits_at_open():
    d = frame([(10, 10, 10, 10), (10, 10, 10, 10), (7, 8, 6, 7), (8, 8, 8, 8)])
    t = simulate(d, sig(d, [0], stop=1.0), C0, "next_open")
    assert t.motivo[0] == "stop_hueco" and t.px_salida[0] == 7


def test_time_exit():
    d = frame([(10, 10, 10, 10)] * 10)
    t = simulate(d, sig(d, [0], md=3), C0, "next_open")
    assert t.motivo[0] == "tiempo" and t.dias[0] == 4          # decide al cierre del día 3 de tenencia, sale al abrir


def test_breakout_window_excludes_today():
    d = frame([(10, 10, 10, 10)] * 25 + [(10, 11, 10, 10.5)])
    s = breakout20(d)
    assert bool(s["entry"].iloc[-1]) is True                     # 10.5 > máximo de los 20 días previos (10)
    assert not s["entry"].iloc[:-1].any()


def test_costs_applied_both_sides():
    d = frame([(10, 10, 10, 10), (10, 10, 10, 10), (10, 10, 10, 10)])
    t = simulate(d, sig(d, [0], [1]), SwingCost(pct_side=0.001, fixed=1.0, capital=1000), "next_open")
    assert abs(t.ret[0] - (-0.002 - 0.002)) < 1e-12
