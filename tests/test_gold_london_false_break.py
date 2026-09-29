"""Pruebas de GOLD_LONDON_FALSE_BREAK_v1.0."""
import numpy as np
import pandas as pd
import pytest

from src.strategies import gold_london_false_break as g


def a(*x):
    return np.array(x, dtype=float)


# ------------------------------------------------------------------------------------- falsa ruptura
def test_first_attack_closing_inside_is_false_break_short():
    h, l, c = a(101, 102.5, 101), a(99, 100, 99), a(100, 100.5, 100)
    est, j, d, primero, _ = g.buscar_falsa_ruptura(h, l, c, [0, 1, 2], 102.0, 98.0)
    assert (est, j, d, primero) == ("SIGNAL", 1, -1, "HIGH")


def test_real_break_spends_extreme_then_other_side_can_signal():
    h, l, c = a(103, 104, 101, 100), a(101, 102, 99, 97), a(102.5, 103, 100, 98.5)
    est, j, d, primero, _ = g.buscar_falsa_ruptura(h, l, c, [0, 1, 2, 3], 102.0, 98.0)
    # vela 0: cierra fuera → HIGH gastado; vela 1 vuelve a superar RH y cierra dentro? cierra 103 (fuera) — da igual
    assert (est, j, d, primero) == ("SIGNAL", 3, 1, "HIGH")


def test_later_false_break_on_spent_extreme_is_ignored():
    h, l, c = a(103, 103, 101), a(101, 100, 99), a(102.5, 101, 100)       # vela 1 cerraría dentro, pero HIGH ya gastado
    assert g.buscar_falsa_ruptura(h, l, c, [0, 1, 2], 102.0, 98.0)[0] == "NO_FALSE_BREAK"


def test_both_sides_same_bar_is_ambiguous():
    h, l, c = a(103), a(97), a(100)
    assert g.buscar_falsa_ruptura(h, l, c, [0], 102.0, 98.0)[0] == "BOTH_SIDES_SAME_BAR"


def test_touch_is_not_a_break():
    h, l, c = a(102.0, 101), a(98.0, 99), a(100, 100)
    assert g.buscar_falsa_ruptura(h, l, c, [0, 1], 102.0, 98.0)[0] == "NO_FALSE_BREAK"


# ---------------------------------------------------------------------------------------- gestión
def test_same_bar_stop_and_target_is_loss_and_time_exit():
    o, h, l, c = a(100, 100), a(103, 101), a(95, 99), a(100, 100.5)
    assert g.gestionar(o, h, l, c, [0, 1], -1, 100.0, 102.0, 96.0)[2] == "SL"
    o, h, l, c = a(100, 100), a(101, 101), a(99, 99), a(100, 99.5)
    m, X, mot, mae, mfe = g.gestionar(o, h, l, c, [0, 1], -1, 100.0, 102.0, 96.0)
    assert (m, X, mot, mae, mfe) == (1, 99.5, "TIME", -1.0, 1.0)


def test_gap_through_stop_exits_at_open():
    o, h, l, c = a(100, 103), a(101, 104), a(99, 102.5), a(100, 103)
    m, X, mot, mae, _ = g.gestionar(o, h, l, c, [0, 1], -1, 100.0, 102.0, 96.0)
    assert (X, mot, mae) == (103.0, "SL", -3.0)


def test_costs_time_exit_takes_market_slippage_in_c():
    assert g.coste_onza(g.ESCENARIOS["C"], "TIME") == pytest.approx(0.77)
    assert g.coste_onza(g.ESCENARIOS["C"], "TP") == pytest.approx(0.47)
    assert g.coste_onza(g.ESCENARIOS["B"], "TIME") == pytest.approx(0.37)


# ------------------------------------------------------------------------------ extremo a extremo
def dia_sintetico(filas, fecha="2024-01-16"):
    """Velas de 15m desde las 08:00 de Londres (enero: Londres = UTC)."""
    idx = pd.date_range(f"{fecha} 08:00", periods=len(filas), freq="15min", tz="UTC")
    m = pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    m["fin"] = m.index + pd.Timedelta(minutes=15)
    m["ajuste"] = 0.0
    return m


def correr(filas, **cfg):
    v = dia_sintetico(filas)
    return g.backtest(None, g.Config(**cfg), prep={"v15": v, "atr": np.zeros(len(v))})


RANGO = [(100, 102, 99, 101)] * 3 + [(101, 101.5, 98, 100)]          # RH = 102, RL = 98


def test_end_to_end_short_after_false_break_of_high():
    filas = RANGO + [(100, 103, 100, 101.5), (101, 101.2, 100, 100.5), (100.5, 100.6, 94, 95)] + [(95, 95, 95, 95)] * 9
    ops, dias = correr(filas)
    op = ops.iloc[0]
    assert (op.entrada, op.sl, op.tp, op.resultado) == (101.0, 103.0, 97.0, "TP")
    assert op.t_entrada == pd.Timestamp("2024-01-16 09:15", tz="UTC")       # apertura de la vela siguiente
    assert op.break_depth == 1.0 and op.break_depth_ratio == 0.25
    assert dias.iloc[0].first_extreme_attacked == "HIGH"


def test_range_frozen_and_signal_window_ends_1130():
    # Falsa ruptura en la vela de 11:45 (fuera de la ventana de señales): no hay operación
    filas = RANGO + [(100, 101, 99, 100)] * 11 + [(100, 103, 100, 101)]
    ops, dias = correr(filas)
    assert ops.empty and dias.iloc[0].estado == "NO_FALSE_BREAK"


def test_time_exit_at_last_bar_before_1200():
    filas = RANGO + [(100, 97.5, 97.5, 99)][:0] + [(100, 100.5, 97.5, 99)] + [(99, 100, 98.5, 99.5)] * 11 + [(90, 90, 90, 90)]
    ops, _ = correr(filas)
    op = ops.iloc[0]
    assert op.resultado == "TIME" and op.salida == 99.5 and op.t_salida == pd.Timestamp("2024-01-16 12:00", tz="UTC")


def test_mnq_costs_in_points_and_point_value():
    # B: 1 tick de entrada + 1 tick de salida a mercado + 1 punto de comisión (2 $ ida y vuelta a 2 $/punto)
    assert g.coste_onza(g.ESCENARIOS_MNQ["B"], "SL") == pytest.approx(1.5)
    assert g.coste_onza(g.ESCENARIOS_MNQ["B"], "TP") == pytest.approx(1.25)
    assert g.coste_onza(g.ESCENARIOS_MNQ["C"], "TIME") == pytest.approx(2.0)
    filas = RANGO + [(100, 103, 100, 101.5), (101, 101.2, 100, 100.5), (100.5, 100.6, 94, 95)] + [(95, 95, 95, 95)] * 9
    ops, _ = correr(filas, valor_punto=2.0, costes=g.ESCENARIOS_MNQ["A"])
    op = ops.iloc[0]
    assert op.onzas == 62 and op.neto_usd == pytest.approx(4 * 62 * 2)    # floor(250 / (2 pt x 2 $)) contratos
