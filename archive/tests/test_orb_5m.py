"""Pruebas de la ORB de 5 minutos y del simulador de trailing de Apex (casos calculados a mano).

MNQ: 1 punto = 2 $, tick 0,25. Comisión 1 $ por contrato y lado. Deslizamiento 1 tick en entrada y stop.
Rango de apertura 9:30-9:45 = 3 velas de 5 minutos.
"""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.risk.apex_trailing import TrailingAccount, monte_carlo, path_summary, run_sequence
from src.strategies.orb_5m import ORB5Config, _run_day, to_bars

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = ORB5Config()  # valores por defecto = los de la especificación


def bars5(rows, start="09:30"):
    idx = pd.date_range(f"{D} {start}", periods=len(rows), freq="5min", tz=TZ)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["volume"] = 100
    df["instrument_id"] = 1
    return df


# Rango: máximo 110, mínimo 100 (ancho 10). Con ATR = 100, el ancho es el 10 %: pasa el filtro.
OPENING = [(105, 110, 102, 104), (104, 108, 100, 101), (101, 106, 101, 105)]
FLAT = (111, 111, 111, 111)


def day_with(after, fill_to_close=True):
    rows = OPENING + after
    if fill_to_close:
        rows += [FLAT] * (78 - len(rows))  # hasta las 16:00
    return bars5(rows)


def test_to_bars_aggregates_minutes():
    idx = pd.date_range(f"{D} 09:30", periods=10, freq="1min", tz=TZ)
    m = pd.DataFrame({"open": range(10), "high": range(1, 11), "low": range(10), "close": range(10),
                      "volume": 1, "instrument_id": 7}, index=idx, dtype=float)
    b = to_bars(m, 5)
    assert list(b.index.strftime("%H:%M")) == ["09:30", "09:35"]
    assert b.iloc[0].tolist()[:5] == [0, 5, 0, 4, 5]


def test_long_to_target():
    # 9:45 cierra en 112 (> 110) -> entrada a las 9:50 en 112 + 0,25 = 112,25
    day = day_with([(109, 112, 109, 112), (112, 113, 111, 112), (112, 137, 112, 136)])
    r = _run_day(DATE, day, 100.0, CFG, set())
    t = r.trade
    assert t["entry"] == 112.25 and t["stop"] == 100
    dist = 12.25
    assert t["qty"] == 6                       # floor(150 / (12,25 * 2)) = 6
    assert t["target"] == pytest.approx(112.25 + 2 * dist)
    assert t["exit_reason"] == "objetivo" and t["exit"] == pytest.approx(136.75)
    assert t["pnl"] == pytest.approx(2 * dist * 2 * 6 - 2 * 1.0 * 6)


def test_stop_first_when_both_in_same_bar():
    day = day_with([(109, 112, 109, 112), (112, 140, 95, 100)])
    t = _run_day(DATE, day, 100.0, CFG, set()).trade
    assert t["exit_reason"] == "stop" and t["exit"] == 99.75   # stop 100 - 1 tick


def test_time_exit_1545():
    after = [(109, 112, 109, 112)] + [(113, 114, 112, 113)] * 70
    day = day_with(after)
    t = _run_day(DATE, day, 100.0, CFG, set()).trade
    assert t["exit_reason"] == "tiempo"
    # La vela de 15:45 es de relleno (abre en 111): se sale a su apertura.
    assert t["exit_time"] == pd.Timestamp(f"{D} 15:45", tz=TZ) and t["exit"] == 111


def test_range_filters():
    day = day_with([(109, 112, 109, 112)])
    assert _run_day(DATE, day, 30.0, CFG, set()).status == "rango_demasiado_ancho"       # 10 > 25 % de 30
    assert _run_day(DATE, day, 300.0, CFG, set()).status == "rango_demasiado_estrecho"   # 10 < 5 % de 300


def test_no_entry_after_1130():
    # Sin ruptura hasta la vela de 11:30 -> la entrada sería a las 11:35 -> no se opera.
    inside = [(105, 109, 101, 105)] * 21                        # 9:45 ... 11:25
    day = day_with(inside + [(105, 112, 105, 112)])            # señal en la vela de 11:30
    assert _run_day(DATE, day, 100.0, CFG, set()).status == "ruptura_despues_de_hora_limite"
    ok = day_with(inside[:-1] + [(105, 112, 105, 112)])        # señal a las 11:25 -> entrada 11:30
    assert _run_day(DATE, ok, 100.0, CFG, set()).status == "operada"


def test_contract_limits():
    day = day_with([(109, 112, 109, 112), (112, 113, 111, 112)])
    wide_risk = CFG.variant(risk_usd=20)                        # 1 contrato arriesga 24,50 $ > 20 $
    assert _run_day(DATE, day, 100.0, wide_risk, set()).status == "riesgo_de_1_contrato_excede_limite"
    big = CFG.variant(risk_usd=10_000)
    assert _run_day(DATE, day, 100.0, big, set()).trade["qty"] == 10   # tope de contratos


def test_news_filter():
    day = day_with([(109, 112, 109, 112)])
    cfg = CFG.variant(news_filter=True)
    assert _run_day(DATE, day, 100.0, cfg, {DATE}).status == "dia_de_noticias"
    assert _run_day(DATE, day, 100.0, CFG, {DATE}).status == "operada"


# ------------------------------------------------------------------ Apex trailing intradía
ACC = TrailingAccount(50_000, 2_000)


def test_unrealized_peak_raises_threshold():
    # La operación llega a +1.500 sin cerrar y acaba en -600: umbral 49.500, saldo 49.400 -> quemada.
    burns = run_sequence([[0, 1500, -600]], ACC, restart=False)
    assert len(burns) == 1 and burns[0]["peak"] == 51_500


def test_survives_without_touching():
    assert run_sequence([[0, 1000, 500], [0, -1400, -1400]], ACC) == []


def test_stop_trailing_cap():
    capped = TrailingAccount(50_000, 2_000, stop_trailing_at=100)
    # Máximo 53.000 -> sin tope el umbral sería 51.000; con tope se queda en 50.100.
    paths = [[0, 3000, 3000], [0, -2500, -2500]]
    assert run_sequence(paths, ACC, restart=False)            # sin tope: 50.500 <= 51.000 -> quemada
    assert run_sequence(paths, capped, restart=False) == []   # con tope: 50.500 > 50.100


def test_monte_carlo_matches_exact_sequence():
    rng = np.random.default_rng(3)
    paths = [list(np.cumsum(rng.normal(0, 300, size=8))) for _ in range(40)]
    s = path_summary(paths)
    # Con operaciones idénticas el orden no importa: el Monte Carlo debe coincidir con la secuencia exacta.
    same = [paths[0]] * 30
    exact_burn = bool(run_sequence(same, ACC, restart=False))
    mc = monte_carlo(path_summary(same), ACC, n_sims=50)
    assert mc["prob_quemar_%"] == (100.0 if exact_burn else 0.0)
    assert set(s.columns) == {"final", "mfe", "mae", "max_dd"}
