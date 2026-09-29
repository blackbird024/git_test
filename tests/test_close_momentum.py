"""Pruebas del momentum de cierre con un día inventado de 390 velas."""
import datetime as dt

from src.engine.types import LONG, SHORT
from src.strategies.close_momentum import CloseMomentum
from tests.conftest import make_bars, ts

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)


def day(first_half_move):
    ohlc = [(100, 100, 100, 100)] * 390
    ohlc[29] = (100, 100, 100, 100 + first_half_move)  # vela de 9:59
    ohlc[349] = (110, 110, 110, 110)                   # vela de 15:19
    return {"MNQ": make_bars(D, ohlc)}


def test_up_morning_goes_long_at_1519():
    sig = CloseMomentum(0.1, {DATE: 50.0}).signals_for_day(DATE, day(+3))[0]
    assert sig.direction == LONG and sig.time == ts(D, "15:19")
    assert sig.stop == 110 - 5 and sig.target == 110 + 10


def test_down_morning_goes_short():
    sig = CloseMomentum(0.2, {DATE: 50.0}).signals_for_day(DATE, day(-3))[0]
    assert sig.direction == SHORT
    assert sig.stop == 110 + 10 and sig.target == 110 - 20


def test_flat_morning_no_trade():
    assert CloseMomentum(0.1, {DATE: 50.0}).signals_for_day(DATE, day(0)) == []
