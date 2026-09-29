"""Pruebas de GOLD_SWING_SIMPLE_v1.0 (swings, barridos, entrada, gestión, ajuste de rolls, look-ahead)."""
import numpy as np
import pandas as pd
import pytest

from src.strategies import gold_swing_simple as g


def a(*x):
    return np.array(x, dtype=float)


# ------------------------------------------------------------------------------------------ swings
def test_swing_needs_two_strictly_lower_bars_each_side():
    h = a(1, 2, 5, 3, 2, 6, 6, 1, 0)
    l = h - 1
    sh, _ = g.swings(h, l, 2)
    assert list(np.flatnonzero(sh)) == [2]          # 6,6 empatados: no es swing (desigualdad estricta)


def test_swing_low_symmetric():
    l = a(5, 4, 1, 3, 4, 0.5, 2, 3)
    _, sl = g.swings(l + 1, l, 2)
    assert list(np.flatnonzero(sl)) == [2, 5]


# ------------------------------------------------------------------------------------- dirección 4H
def v4(highs, lows):
    idx = pd.date_range("2024-01-01", periods=len(highs), freq="4h", tz="UTC")
    return pd.DataFrame({"high": highs, "low": lows}, index=idx)


def test_direction_uses_only_confirmed_swings():
    # SH en 2 (10) y 6 (12); SL en 4 (5) y 8 (6): alcista, pero solo cuando se confirma el SL de la vela 8 (j = 10)
    highs = a(8, 9, 10, 9, 8, 9, 12, 11, 9, 10, 11, 12)
    lows = a(6, 7, 7, 6, 5, 7, 9, 8, 6, 7, 8, 9)
    d = g.direccion_4h(v4(highs, lows), 2)
    assert list(d[:10]) == [0] * 10
    assert d[10] == 1


# ------------------------------------------------------------------------------------------ barridos
def v1(filas):
    idx = pd.date_range("2024-01-01", periods=len(filas), freq="1h", tz="UTC")
    return pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)


BASE = [(10, 11, 9, 10), (10, 11, 8, 10), (10, 11, 5, 10), (10, 11, 8, 10), (10, 11, 9, 10)]  # SL = 5 en la vela 2


def test_sweep_low_detected_after_confirmation():
    ev = g.barridos(v1(BASE + [(10, 11, 4, 6)]), 2)              # mecha a 4, cierra en 6 > 5
    assert ev == [{"b": 5, "d": 1, "nivel": 5.0, "i_swing": 2}]


def test_break_consumes_level_without_sweep():
    ev = g.barridos(v1(BASE + [(10, 11, 4, 4.5), (6, 7, 4, 6)]), 2)  # primera vela cierra debajo: ruptura
    assert ev == []


def test_swing_not_usable_before_confirmed():
    # La vela 4 (i + 2) confirma el swing; una vela 3 que baje de 5 no puede barrerlo (y además rompe el swing)
    filas = [(10, 11, 9, 10), (10, 11, 8, 10), (10, 11, 5, 10), (10, 11, 4, 6)]
    assert g.barridos(v1(filas), 2) == []


# ------------------------------------------------------------------------------------ entrada y gestión
def v15(filas):
    idx = pd.date_range("2024-01-01", periods=len(filas), freq="15min", tz="UTC")
    df = pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    return df.open.to_numpy(), df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(), idx.asi8


def test_entry_on_touch_of_midpoint_long():
    o, h, l, c, ini = v15([(110, 111, 106, 107), (107, 108, 104.9, 105), (105, 106, 104, 105)])
    k, E, mot = g.buscar_entrada(o, h, l, ini, ini[0], ini[-1] + 10**12, 1, 100.0, 110.0, 105.0)
    assert (k, E, mot) == (1, 105.0, None)


def test_gap_through_zone_cancels():
    o, h, l, c, ini = v15([(110, 111, 106, 107), (99, 100, 98, 99)])     # abre debajo de la zona [100, 110]
    assert g.buscar_entrada(o, h, l, ini, ini[0], ini[-1] + 10**12, 1, 100.0, 110.0, 105.0)[2] == "CANCEL_TRAVERSED"


def test_open_inside_zone_fills_at_open():
    o, h, l, c, ini = v15([(103, 104, 102, 103)])
    k, E, _ = g.buscar_entrada(o, h, l, ini, ini[0], ini[-1] + 10**12, 1, 100.0, 110.0, 105.0)
    assert E == 103.0


def test_no_entry_after_cancel_time():
    o, h, l, c, ini = v15([(110, 111, 106, 107), (107, 108, 104, 105)])
    k, E, mot = g.buscar_entrada(o, h, l, ini, ini[0], ini[1], 1, 100.0, 110.0, 105.0)
    assert k is None and mot is None


def test_stop_and_target_same_bar_is_loss():
    o, h, l, c, _ = v15([(105, 106, 104, 105), (105, 115, 95, 100)])
    m, X, mot, mae, mfe = g.gestionar(o, h, l, c, 0, 1, 105.0, 100.0, 115.0)
    assert (m, X, mot, mae) == (1, 100.0, "SL", -5.0)            # MAE hasta el precio de salida


def test_fill_bar_counts_stop_only():
    o, h, l, c, _ = v15([(105, 116, 104, 110), (110, 111, 109, 110)])      # objetivo tocado en la vela del llenado
    m, X, mot, _, _ = g.gestionar(o, h, l, c, 0, 1, 105.0, 100.0, 115.0)
    assert mot == "END_OF_DATA"


def test_gap_through_stop_exits_at_open():
    o, h, l, c, _ = v15([(105, 106, 104, 105), (97, 98, 96, 97)])
    m, X, mot, mae, _ = g.gestionar(o, h, l, c, 0, 1, 105.0, 100.0, 115.0)
    assert (X, mot) == (97.0, "SL") and mae == -8.0          # MAE hasta la salida (apertura con hueco)


def test_target_hit_and_mfe_capped():
    o, h, l, c, _ = v15([(105, 106, 103, 105), (105, 120, 104, 118)])
    m, X, mot, mae, mfe = g.gestionar(o, h, l, c, 0, 1, 105.0, 100.0, 115.0)
    assert (X, mot, mae, mfe) == (115.0, "TP", -2.0, 10.0)


def test_entry_price_modes():
    assert g.precio_entrada(1, 100, 110, "mitad") == 105
    assert g.precio_entrada(1, 100, 110, "cercano") == 110 and g.precio_entrada(1, 100, 110, "lejano") == 100
    assert g.precio_entrada(-1, 100, 110, "cercano") == 100 and g.precio_entrada(-1, 100, 110, "lejano") == 110


def test_costs_per_ounce():
    assert g.ESCENARIOS["A"].por_onza("SL") == 0
    assert g.ESCENARIOS["B"].por_onza("TP") == pytest.approx(0.37)
    assert g.ESCENARIOS["C"].por_onza("SL") == pytest.approx(0.77) and g.ESCENARIOS["C"].por_onza("TP") == pytest.approx(0.47)


# ---------------------------------------------------------------------------------------- rolls
def test_back_adjust_keeps_differences_and_removes_gap():
    idx = pd.date_range("2024-01-01", periods=4, freq="1min", tz="UTC")
    m = pd.DataFrame({"open": [100, 101, 110, 111], "high": [100, 101, 110, 111], "low": [100, 101, 110, 111],
                      "close": [100, 101, 110, 111], "instrument_id": [1, 1, 2, 2]}, index=idx, dtype=float)
    a_ = g.ajustar_rolls(m)
    assert list(a_.close) == [109, 110, 110, 111]                 # salto 110 - 101 = 9 sumado al pasado
    assert a_.attrs["rolls"] == [idx[2]]
