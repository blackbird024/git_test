"""Pruebas de GOLD_MA_TREND_v1.0."""
import numpy as np
import pandas as pd
import pytest

from src.strategies import gold_ma_trend as g


def diario(closes, ids=None, opens=None):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="B", tz="UTC")
    c = np.array(closes, float)
    o = c if opens is None else np.array(opens, float)
    d = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 1, "low": np.minimum(o, c) - 1, "close": c,
                      "volume": 1, "instrument_id": ids or [1] * len(c)}, index=idx)
    d["ajuste"] = 0.0
    return d


def test_sunday_merged_into_monday_and_trailing_sunday_dropped():
    idx = pd.DatetimeIndex(["2024-01-05", "2024-01-07", "2024-01-08", "2024-01-14"], tz="UTC")  # vie, dom, lun, dom
    df = pd.DataFrame({"open": [1, 2, 3, 4], "high": [5, 9, 6, 7], "low": [0, 1.5, 2, 3], "close": [1, 2, 3, 4],
                       "volume": [10, 1, 10, 1], "instrument_id": [1, 1, 1, 1]}, index=idx, dtype=float)
    u = g.unir_domingos(df)
    assert list(u.index.dayofweek) == [4, 0]
    lunes = u.iloc[1]
    assert (lunes.open, lunes.high, lunes.low, lunes.close, lunes.volume) == (2, 9, 1.5, 3, 11)


def test_regime_uses_only_past_and_keeps_on_ties():
    c = pd.Series([1, 2, 3, 4, 3, 2, 1, 1.0])
    reg = g.regimen(c, 2, 3)
    assert list(reg) == [0, 0, 1, 1, 1, -1, -1, -1]                   # día 4: SMA2 3,5 > SMA3 3,33
    assert list(g.regimen(c.iloc[:5], 2, 3)) == list(reg[:5])          # añadir datos no cambia el pasado
    empate = g.regimen(pd.Series([1, 2, 3, 3, 3, 3.0]), 2, 3)         # días 4 y 5: SMA2 = SMA3 = 3
    assert list(empate) == [0, 0, 1, 1, 1, 1]


def test_first_position_only_after_first_cross():
    reg = np.array([0, 1, 1, -1, -1, 1])
    assert list(g.objetivo(reg, False)) == [0, 0, 0, -1, -1, 1]
    assert list(g.objetivo(reg, True)) == [0, 0, 0, 0, 0, 1]


def test_execution_at_next_open_not_signal_close(monkeypatch):
    d = diario([10, 10, 10, 10, 10], opens=[10, 10, 10, 12, 13])
    monkeypatch.setattr(g, "regimen", lambda c, f, s: np.array([0, 1, -1, -1, -1]))   # cruce al cierre del día 2
    ops, di = g.simular(d, g.Config(costes=g.ESCENARIOS[0]))
    op = ops.iloc[0]
    assert op.dia_senal == d.index[2] and op.dia_entrada == d.index[3] and op.entrada == 12.0   # apertura de D+1
    assert op.direccion == -1 and di.pos.iloc[2] == 0 and di.pos.iloc[3] == -1


def test_costs_and_roll_cost(monkeypatch):
    d = diario([10] * 6, ids=[1, 1, 1, 1, 2, 2])
    monkeypatch.setattr(g, "regimen", lambda c, f, s: np.array([0, 1, -1, -1, -1, -1]))
    ops, di = g.simular(d, g.Config(costes=g.ESCENARIOS[1]))
    op = ops.iloc[0]
    assert op.rolls == 1 and op.abierta_al_final
    assert op.costes_usd == pytest.approx(12.5 + 25.0)                   # entrada + un roll (sale al final: marcada)
    assert di.coste.sum() == pytest.approx(12.5 + 25.0)


def test_reversal_closes_and_opens_same_bar(monkeypatch):
    d = diario([10, 11, 12, 13, 14, 15])
    monkeypatch.setattr(g, "regimen", lambda c, f, s: np.array([0, 1, -1, 1, 1, 1]))
    ops, _ = g.simular(d, g.Config(costes=g.ESCENARIOS[0]))
    assert list(ops.direccion) == [-1, 1]
    assert ops.dia_salida.iloc[0] == ops.dia_entrada.iloc[1]                # sin posiciones simultáneas
    assert ops.neto_usd.iloc[0] == pytest.approx(-(13 - 12) * 100)
