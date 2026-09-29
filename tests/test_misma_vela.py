"""Cálculo de stop y objetivo: misma vela = pérdida; huecos; objetivo sin deslizamiento; costes."""
import pandas as pd
import pytest

from src.engine.costes import Costes
from src.engine.ejecucion import ejecutar

TICK, PV = 0.25, 2.0                      # MNQ
C = Costes(comision_lado=1.0)            # 1 tick normal, 2 en aperturas


def velas(filas, inicio="2024-01-15 17:00"):  # 17:00 UTC = 12:00 NY: fuera de aperturas
    idx = pd.date_range(inicio, periods=len(filas), freq="1min", tz="UTC")
    return pd.DataFrame(filas, columns=["open", "high", "low", "close"], index=idx, dtype=float)


LIMITE = pd.Timestamp("2024-01-16", tz="UTC")


def test_stop_and_target_same_bar_is_a_loss():
    v = velas([(100, 100, 100, 100), (100, 100, 100, 100), (100, 115, 85, 100)])
    op = ejecutar(v, 0, 1, stop=90, objetivo=110, contratos=1, t_limite=LIMITE, tick=TICK, valor_punto=PV, costes=C)
    assert op.motivo == "stop" and op.salida == 89.75 and op.neto < 0


def test_entry_is_next_bar_open_with_slippage():
    v = velas([(100, 100, 100, 100), (101, 101, 101, 101), (101, 111, 101, 110)])
    op = ejecutar(v, 0, 1, stop=90, objetivo=110, contratos=1, t_limite=LIMITE, tick=TICK, valor_punto=PV, costes=C)
    assert op.t_entrada == v.index[1] and op.entrada == 101.25
    assert op.motivo == "objetivo" and op.salida == 110                       # límite: sin deslizamiento
    assert op.neto == pytest.approx((110 - 101.25) * 2 - 2.0)


def test_gap_through_stop_fills_at_open():
    v = velas([(100, 100, 100, 100), (100, 100, 100, 100), (80, 81, 79, 80)])
    op = ejecutar(v, 0, 1, stop=90, objetivo=None, contratos=1, t_limite=LIMITE, tick=TICK, valor_punto=PV, costes=C)
    assert op.salida == 79.75


def test_two_ticks_at_london_open():
    v = velas([(100, 100, 100, 100), (100, 100, 100, 100)], inicio="2024-01-15 07:59")  # 08:00 Londres
    op = ejecutar(v, 0, -1, stop=110, objetivo=None, contratos=1, t_limite=LIMITE, tick=TICK, valor_punto=PV, costes=C)
    assert op.entrada == 100 - 2 * 0.25


def test_doubled_costs():
    v = velas([(100, 100, 100, 100), (100, 100, 100, 100), (100, 111, 100, 110)])
    op = ejecutar(v, 0, 1, stop=90, objetivo=110, contratos=1, t_limite=LIMITE, tick=TICK, valor_punto=PV,
                  costes=Costes(multiplicador=2.0))
    assert op.entrada == 100.5 and op.comision == 4.0


def test_time_exit():
    v = velas([(100, 100, 100, 100)] * 3 + [(105, 105, 105, 105)])
    op = ejecutar(v, 0, 1, stop=90, objetivo=None, contratos=1, t_limite=v.index[3], tick=TICK, valor_punto=PV, costes=C)
    assert op.motivo == "tiempo" and op.salida == 104.75
