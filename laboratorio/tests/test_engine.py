"""Pruebas de las reglas esenciales del simulador y de las estrategias (casos sintéticos, resultados exactos)."""
import numpy as np
import pandas as pd
import pytest

from backtests.intraday import Order, simulate
from data.loaders import Session, bars5, et_to_rome
from execution_costs.costs import FutCost
from strategies.orb import orb

C0 = FutCost(point_value=2.0, tick=0.25, fixed_per_side=0.0, slip_ticks=0, limit_cross_ticks=1)
C1 = FutCost(point_value=2.0, tick=0.25, fixed_per_side=0.0, slip_ticks=1, limit_cross_ticks=1)


def flat(price=100.0, n=390):
    m = np.full((390, 5), np.nan)
    m[:n] = [price, price, price, price, 10]
    return m


def bar(m, k, o, h, l, c):
    m[k, :4] = (o, h, l, c)


def test_market_entry_with_slippage_and_time_exit():
    m = flat()
    f = simulate("d", m, 390, Order(1, "market", 10, 95, None, 20), C1)
    assert f.entry == 100.25 and f.exit == 99.75 and f.reason == "tiempo" and f.exit_k == 20


def test_stop_first_when_stop_and_target_in_same_bar():
    m = flat()
    bar(m, 11, 100, 120, 90, 100)
    f = simulate("d", m, 390, Order(1, "market", 10, 95, 110, 300), C0)
    assert f.reason == "stop" and f.exit == 95


def test_gap_through_stop_fills_at_open():
    m = flat()
    bar(m, 12, 90, 91, 89, 90)
    f = simulate("d", m, 390, Order(1, "market", 10, 95, None, 300), C1)
    assert f.reason == "stop_hueco" and f.exit == 90 - 0.25


def test_target_needs_one_tick_through():
    m = flat()
    bar(m, 12, 100, 110, 100, 100)                # toca exactamente el objetivo: no se llena
    bar(m, 13, 100, 110.25, 100, 100)             # lo cruza 1 tick: se llena al objetivo
    f = simulate("d", m, 390, Order(1, "market", 10, 95, 110, 300), C0)
    assert f.reason == "objetivo" and f.exit_k == 13 and f.exit == 110


def test_target_r_from_effective_entry():
    m = flat()
    bar(m, 15, 100, 111, 100, 100)
    f = simulate("d", m, 390, Order(1, "market", 10, 95, None, 300, target_r=2.0), C1)
    # entrada 100.25, riesgo 5.25, objetivo 110.75
    assert f.target == pytest.approx(110.75) and f.reason == "objetivo"


def test_entry_beyond_stop_is_cancelled():
    m = flat()
    assert simulate("d", m, 390, Order(1, "market", 10, 100.5, None, 300), C0) is None


def test_stop_entry_gap_fill_and_no_target_on_entry_bar():
    m = flat()
    bar(m, 20, 103, 130, 103, 120)                # abre por encima del nivel 101 → se llena en 103
    f = simulate("d", m, 390, Order(1, "stop", 5, 99, None, 300, level=101, k_last=90, target_r=1.0), C0)
    assert f.entry == 103 and f.entry_k == 20 and f.reason != "objetivo"


def test_half_day_exits_at_session_close():
    m = flat(n=210)
    f = simulate("d", m, 210, Order(1, "market", 10, 95, None, 385), C0)
    assert f.reason == "cierre_sesion" and f.exit_k == 209


def test_bars5_alignment():
    m = flat()
    m[1:4] = np.nan
    bar(m, 0, 1, 5, 0.5, 2); bar(m, 4, 2, 3, 1, 4)
    s = Session(pd.Timestamp("2024-01-02"), m, 390, 1, False)
    b = bars5(s)
    assert b.shape == (78, 4) and tuple(b[0]) == (1, 5, 0.5, 4)


def _orb_session(path5):
    """Sesión sintética: rango 9:30-9:35 de 100 a 101, luego velas de 5 min dadas (o,h,l,c) repartidas en 1 min."""
    m = flat(100.5)
    for k in range(5):
        bar(m, k, 100.5, 101, 100, 100.5)
    for i, (o, h, l, c) in enumerate(path5, start=1):
        for j in range(5):
            bar(m, 5 * i + j, o if j == 0 else c, h, l, c)
    return Session(pd.Timestamp("2024-01-02"), m, 390, 1, False)


def test_orb_close_entry_next_open():
    s = _orb_session([(100.5, 101.5, 100.5, 101.5)])
    o = orb(s, {}, variant="close")
    assert o.side == 1 and o.kind == "market" and o.k == 10 and o.stop == 99.75


def test_orb_retest_requires_touch_and_close_beyond():
    # ruptura (vela 1), vela 2 no toca, vela 3 toca 101.25 (≤ ORH + 2 ticks) y cierra 101.75 → entrada vela 4
    s = _orb_session([(100.5, 102, 100.5, 102), (102, 103, 101.8, 102.5), (102.5, 102.5, 101.25, 101.75)])
    o = orb(s, {}, variant="retest")
    assert o is not None and o.k == 20 and o.stop == 101.0 and o.target_r == 2.0


def test_orb_retest_invalidated_by_close_inside():
    s = _orb_session([(100.5, 102, 100.5, 102), (102, 102, 100.5, 100.8), (100.8, 101.5, 101, 101.5)])
    assert orb(s, {}, variant="retest") is None


def test_orb_retest_window_three_bars():
    s = _orb_session([(100.5, 102, 100.5, 102)] + [(102, 103, 102, 102.5)] * 3 + [(102.5, 102.5, 101, 101.5)])
    assert orb(s, {}, variant="retest") is None


def test_rome_time_handles_both_dst_changes():
    assert et_to_rome("2026-03-16", "09:30") == "14:30"     # EE. UU. ya en verano, Europa todavía no
    assert et_to_rome("2026-04-06", "09:30") == "15:30"
    assert et_to_rome("2026-10-30", "09:30") == "14:30"     # Europa ya en invierno, EE. UU. todavía no
    assert et_to_rome("2026-11-05", "09:30") == "15:30"


def test_limit_entry_needs_cross_and_cancels_if_stop_first():
    m = flat()
    bar(m, 12, 100, 100.5, 99.5, 100)             # toca el nivel 100.5 pero no lo cruza: sin entrada
    bar(m, 13, 100, 100.75, 99.5, 100)            # lo cruza 1 tick: venta límite a 100.5
    bar(m, 20, 100, 100, 94, 95)
    f = simulate("d", m, 390, Order(-1, "limit", 10, 102, None, 300, level=100.5, k_last=60, target_r=1.0), C1)
    assert f.entry == 100.5 and f.entry_k == 13 and f.reason == "objetivo"     # sin deslizamiento en la entrada límite
    m2 = flat()
    bar(m2, 12, 100, 103, 100, 100)               # toca el stop (102) en la misma vela que cruzaría la entrada
    f2 = simulate("d", m2, 390, Order(-1, "limit", 10, 102, None, 300, level=100.5, k_last=60), C1)
    assert f2.reason in ("stop", "stop_hueco")    # entra y sale por stop (conservador)
    m3 = flat()
    bar(m3, 12, 100, 100.25, 99, 99)
    bar(m3, 13, 99, 99, 90, 90)                   # nunca vuelve al nivel
    assert simulate("d", m3, 390, Order(-1, "limit", 10, 102, None, 300, level=100.5, k_last=60), C1) is None
