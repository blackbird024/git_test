"""Pruebas de GOLD_SWING_MINIMAL_v1.0."""
import numpy as np
import pandas as pd
import pytest

from src.strategies import gold_swing_minimal as g


def v1(filas, inicio="2024-01-01"):
    idx = pd.date_range(inicio, periods=len(filas), freq="1h", tz="UTC")
    v = pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    v["fin"] = v.index + pd.Timedelta(hours=1)
    return v


def correr(filas, d=1, **cfg):
    """Backtest con dirección 4H fija (`d`) y ATR 0, para probar solo la lógica de 1H."""
    v = v1(filas)
    v4 = pd.DataFrame({"close": [1.0], "fin": [v.index[0]]}, index=[v.index[0] - pd.Timedelta(hours=4)])
    prep = {"v1": v, "v4": v4, "rolls": [], "atr": np.zeros(len(v))}
    orig = g.direccion_4h
    g.direccion_4h = lambda v4_, n: np.array([d])
    try:
        return g.backtest(None, g.Config(**cfg), prep)
    finally:
        g.direccion_4h = orig


def test_ema_direction_uses_only_past_and_warmup():
    idx = pd.date_range("2024-01-01", periods=60, freq="4h", tz="UTC")
    v4 = pd.DataFrame({"close": np.r_[np.full(55, 100.0), [110, 90, 90, 90, 120]]}, index=idx)
    d = g.direccion_4h(v4, 50)
    assert (d[:50] == 0).all() and d[55] == 1 and d[56] == -1
    d_trunc = g.direccion_4h(v4.iloc[:57], 50)
    assert (d_trunc == d[:57]).all()                            # añadir velas futuras no cambia el pasado


def test_direction_on_1h_uses_last_closed_4h():
    v = v1([(1, 1, 1, 1)] * 8)
    v4 = pd.DataFrame({"fin": [v.index[0] + pd.Timedelta(hours=4)]}, index=[v.index[0]])
    d = g.direccion_en_1h(v, v4, np.array([1]))
    assert list(d) == [0, 0, 0, 1, 1, 1, 1, 1]                 # la 1H que cierra a las 04:00 ya ve la 4H cerrada


BASE = [(100, 101, 99, 100), (100, 101, 98, 99), (99, 102.5, 99, 102), (102, 103, 101, 102)]
# vela 1: retroceso (99 < 100); vela 2: señal (102 > máximo anterior 101); entrada en la apertura de la vela 3 = 102


def test_long_signal_entry_next_open_stop_pullback_low():
    ops, sen = correr(BASE + [(102, 110, 101.5, 109)])
    op = ops.iloc[0]
    assert op.entrada == 102 and op.sl == 98 and op.tp == 110 and op.t_entrada == v1(BASE).index[3]
    assert op.resultado == "TP"


def test_same_bar_stop_and_target_is_loss():
    ops, _ = correr(BASE[:3] + [(102, 111, 97, 105)])
    assert ops.iloc[0].resultado == "SL" and ops.iloc[0].salida == 98


def test_new_pullback_resets_stop():
    filas = [(100, 101, 99, 100), (100, 101, 98, 99), (99, 100, 96, 98.5), (98.5, 101, 98, 100.8), (101, 103, 100, 101)]
    ops, _ = correr(filas + [(101, 120, 100.5, 119)])
    assert ops.iloc[0].sl == 96                                 # el segundo retroceso (vela 2) reinicia el stop


def test_window_expires_after_5_bars():
    filas = [(100, 101, 99, 100), (100, 110, 98, 99)] + [(99, 100, 99, 99.5), (99.5, 100, 99, 99.6),
                                                          (99.6, 100, 99, 99.7), (99.7, 100, 99, 99.8),
                                                          (99.8, 100, 99, 99.9)] + [(99.9, 101, 99.8, 100.5)]
    ops, sen = correr(filas + [(100.5, 101, 100, 100.5)])
    assert ops.empty and sen.empty                              # la vela 7 superaría el máximo, pero ya caducó


def test_short_symmetric():
    filas = [(100, 101, 99, 100), (100, 102, 99, 101), (101, 101, 97.5, 98), (98, 99, 97, 98)]
    ops, _ = correr(filas + [(98, 99, 90, 91)], d=-1)
    op = ops.iloc[0]
    assert (op.entrada, op.sl, op.tp, op.resultado) == (98, 102, 90, "TP")


def test_signals_ignored_while_trade_open():
    filas = BASE + [(102, 103, 100, 101), (101, 104, 100.5, 103.5), (103.5, 104, 103, 103.5)] + [(103.5, 110, 103, 109)]
    ops, sen = correr(filas)
    assert len(ops) == 1 and "IGNORED_TRADE_OPEN" in set(sen.estado)


def test_gap_through_stop_exits_at_open_and_costs():
    ops, _ = correr(BASE[:3] + [(102, 102, 101, 101), (95, 96, 94, 95)])
    op = ops.iloc[0]
    assert op.salida == 95 and op.r == pytest.approx((95 - 102 - 0.37) / 4)
