"""Pruebas de la estrategia ORB con un día inventado."""
import datetime as dt

from src.engine.types import LONG, SHORT
from src.strategies.orb import ORB
from tests.conftest import make_bars, ts

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)


def day(after_range):
    # 5 velas de rango de apertura: máximo 105, mínimo 95
    opening = [(100, 105, 99, 101), (101, 103, 95, 97), (97, 100, 96, 99), (99, 101, 98, 100), (100, 102, 99, 101)]
    return {"MNQ": make_bars(D, opening + after_range)}


def test_long_breakout_range_stop():
    bars = day([(101, 104, 100, 104), (104, 107, 103, 106), (106, 108, 104, 107)])
    sig = ORB(5, "range", {DATE: 40.0}).signals_for_day(DATE, bars)[0]
    assert sig.direction == LONG
    assert sig.time == ts(D, "09:36")  # primera vela que CIERRA por encima de 105
    assert sig.stop == 95
    assert sig.target == 106 + 1.5 * (106 - 95)


def test_short_breakout_atr_stop():
    bars = day([(100, 101, 93, 94)])
    sig = ORB(5, "atr", {DATE: 40.0}).signals_for_day(DATE, bars)[0]
    assert sig.direction == SHORT
    assert sig.stop == 94 + 0.25 * 40
    assert sig.target == 94 - 1.5 * 10


def test_no_signal_without_atr_or_breakout():
    bars = day([(100, 104, 96, 100)] * 3)
    assert ORB(5, "range", {DATE: 40.0}).signals_for_day(DATE, bars) == []
    assert ORB(5, "range", {}).signals_for_day(DATE, day([(101, 107, 100, 106)])) == []


def test_breakout_inside_opening_range_is_ignored():
    # Con rango de 15 minutos, la vela de las 9:36 aún forma parte del rango: no es señal.
    bars = day([(101, 107, 100, 106)] + [(106, 106, 104, 105)] * 12)
    sigs = ORB(15, "range", {DATE: 40.0}).signals_for_day(DATE, bars)
    assert sigs == []
