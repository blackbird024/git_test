"""Pruebas de la estrategia VWAP con un día inventado."""
import datetime as dt

import pandas as pd

from src.engine.types import LONG, SHORT
from src.strategies.vwap_trend import VWAPTrend, session_vwap
from tests.conftest import make_bars, ts

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)


def test_session_vwap_weights_by_volume():
    df = make_bars(D, [(10, 10, 10, 10), (20, 20, 20, 20)])
    df["volume"] = [300, 100]
    assert session_vwap(df).iloc[-1] == (10 * 300 + 20 * 100) / 400


def uptrend_with_pullback():
    # 40 velas subiendo desde 100; la de las 10:05 se sustituye por una que toca el VWAP y cierra encima.
    ohlc = [(100 + i, 101 + i, 99.5 + i, 100.5 + i) for i in range(40)]
    df = make_bars(D, ohlc).astype(float)
    vwap = session_vwap(df)
    t = ts(D, "10:05")
    v = vwap.loc[t]
    df.loc[t, ["open", "high", "low", "close"]] = [v + 5, v + 6, v - 0.5, v + 3]
    return {"MNQ": df}, t


def test_long_pullback_signal():
    bars, t = uptrend_with_pullback()
    sig = VWAPTrend("MNQ", 0.1, {DATE: 50.0}).signals_for_day(DATE, bars)[0]
    assert sig.direction == LONG and sig.time == t
    vwap = session_vwap(bars["MNQ"]).loc[t]
    assert abs(sig.stop - (vwap - 5.0)) < 1e-9
    assert sig.target > sig.stop


def test_no_signal_before_10():
    ohlc = [(100, 101, 99, 100.5)] * 20  # 9:30-9:49: toca el VWAP, pero antes de las 10:00
    bars = {"MNQ": make_bars(D, ohlc)}
    assert VWAPTrend("MNQ", 0.1, {DATE: 50.0}).signals_for_day(DATE, bars) == []


def test_short_mirror():
    bars, t = uptrend_with_pullback()
    df = bars["MNQ"]
    mirrored = df.copy()
    mirrored[["open", "close"]] = 300 - df[["open", "close"]]
    mirrored["high"], mirrored["low"] = 300 - df.low, 300 - df.high
    sig = VWAPTrend("MNQ", 0.1, {DATE: 50.0}).signals_for_day(DATE, {"MNQ": mirrored})[0]
    assert sig.direction == SHORT and sig.time == t
    assert isinstance(sig.time, pd.Timestamp)
