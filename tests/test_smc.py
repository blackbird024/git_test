"""Pruebas del SMC (barrido + desplazamiento + FVG) y de la orden límite del motor."""
import numpy as np
import pandas as pd
import pytest

from src.engine.costes import Costes
from src.engine.ejecucion import ejecutar_limite
from src.strategies.smc_sweep import ORO, buscar_patron

C = Costes()
LIM = pd.Timestamp("2024-01-16", tz="UTC")


def v1(filas, inicio="2024-01-15 12:00"):
    idx = pd.date_range(inicio, periods=len(filas), freq="1min", tz="UTC")
    return pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)


# ------------------------------------------------------------------------------ orden límite
def test_limit_needs_one_tick_through():
    v = v1([(100, 100, 100, 100), (100, 101.0, 99.9, 100.5), (100.5, 101.1, 100.4, 101.0), (101, 101, 95, 95)])
    op = ejecutar_limite(v, 1, -1, 101.0, 105.0, 95.5, 1, LIM, LIM, 0.1, 10.0, C)
    assert op.t_entrada == v.index[2] and op.entrada == 101.0      # la vela 1 solo lo toca; la 2 lo cruza
    assert op.motivo == "objetivo" and op.salida == 95.5


def test_limit_cancelled_if_target_first():
    v = v1([(100, 100, 100, 100), (100, 100.2, 94.0, 95.0), (95, 102, 95, 101)])
    assert ejecutar_limite(v, 1, -1, 101.0, 105.0, 95.5, 1, LIM, LIM, 0.1, 10.0, C) is None


def test_fill_bar_counts_stop_but_not_target():
    solo_obj = v1([(100, 100, 100, 100), (100, 101.2, 95.0, 96.0), (96, 96, 96, 96)])
    op = ejecutar_limite(solo_obj, 1, -1, 101.0, 105.0, 95.5, 1, LIM, pd.Timestamp("2024-01-15 12:02", tz="UTC"),
                         0.1, 10.0, C)
    assert op.motivo == "tiempo"                                   # el objetivo en la vela del llenado no cuenta
    con_stop = v1([(100, 100, 100, 100), (100, 105.5, 99, 104)])
    op = ejecutar_limite(con_stop, 1, -1, 101.0, 105.0, 95.5, 1, LIM, LIM, 0.1, 10.0, C)
    assert op.motivo == "stop" and op.salida == pytest.approx(105.1)


def test_limit_expires():
    v = v1([(100, 100, 100, 100)] * 5)
    assert ejecutar_limite(v, 1, -1, 101.0, 105.0, 95.5, 1, v.index[3], LIM, 0.1, 10.0, C) is None


# ---------------------------------------------------------------------------------- patrón
def v5(filas):
    idx = pd.date_range("2024-01-15 09:00", periods=len(filas), freq="5min", tz="UTC")
    df = pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["atr"] = 1.0
    return df


def test_pattern_sweep_return_displacement_fvg():
    # Nivel (PDH) = 100. Barrido en la vela 1, vuelta dentro en la 2, desplazamiento bajista en la 3 (cuerpo 2 >= 1,5),
    # FVG bajista: máximo de la vela 4 (98,8) < mínimo de la vela 2 (99,0).
    filas = [(99.5, 99.8, 99.2, 99.6), (99.6, 100.6, 99.5, 100.2), (100.2, 100.3, 99.0, 99.4),
             (99.4, 99.5, 97.3, 97.4), (97.4, 98.8, 97.0, 98.0), (98, 98, 98, 98)]
    p = buscar_patron(v5(filas), 0, len(filas), 100.0, -1, ORO)
    assert p is not None
    c3, extremo, limite, i_barrido = p
    assert (c3, extremo, limite, i_barrido) == (4, 100.6, 98.8, 1)


def test_no_pattern_without_displacement():
    filas = [(99.5, 99.8, 99.2, 99.6), (99.6, 100.6, 99.5, 100.2), (100.2, 100.3, 99.0, 99.4),
             (99.4, 99.5, 98.5, 98.6), (98.6, 98.8, 98.0, 98.2), (98, 98, 98, 98)]   # cuerpos < 1,5 x ATR
    assert buscar_patron(v5(filas), 0, len(filas), 100.0, -1, ORO) is None


def test_no_pattern_if_first_cross_does_not_come_back():
    filas = [(99.5, 99.8, 99.2, 99.6)] + [(100.5, 101, 100.2, 100.8)] * 7
    assert buscar_patron(v5(filas), 0, len(filas), 100.0, -1, ORO) is None
