"""Pruebas del motor con casos calculados a mano.

Instrumento de prueba MNQ: tick 0,25; 1 punto = 2 $; comisión 1,50 $ ida y vuelta;
deslizamiento de 1 tick (0,25 puntos) por lado.
"""
import pandas as pd
import pytest

from src.engine.backtest import Backtester
from src.engine.types import LONG, SHORT, Signal
from src.risk.sizing import contracts_for_risk
from tests.conftest import FixedSignals, make_bars, ts

D = "2024-03-04"


def run(instruments, rules, data, signals, max_micros=60):
    return Backtester(instruments, rules, max_micros).run(data, [FixedSignals(signals)])


def test_sizing(instruments):
    # Stop a 30 puntos: 30,25 * 2 + 1,5 = 62 $ por contrato -> 150 / 62 = 2,4 -> 2 contratos
    assert contracts_for_risk(instruments["MNQ"], 100.0, 70.0, 150) == 2
    # Stop demasiado lejano: no cabe ni 1 contrato
    assert contracts_for_risk(instruments["MNQ"], 100.0, 0.0, 150) == 0


def test_long_hits_target(instruments, rules):
    bars = make_bars(D, [(100, 101, 99, 100),     # 09:30 señal al cierre
                         (100, 102, 99.5, 101),   # 09:31 entrada en 100 + 0,25 = 100,25
                         (101, 112, 100, 111)])   # 09:32 toca objetivo 110
    sig = Signal("t", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    res = run(instruments, rules, {"MNQ": bars}, [sig])
    t = res.trades.iloc[0]
    # Riesgo por contrato = (10,25 + 0,25) * 2 + 1,5 = 22,5 $ -> 150 / 22,5 = 6 contratos
    assert t.qty == 6
    assert t.entry_price == 100.25
    assert t.exit_reason == "target" and t.exit_price == 110
    assert t.pnl_net == pytest.approx((110 - 100.25) * 2 * 6 - 1.5 * 6)


def test_stop_wins_when_both_touched_same_bar(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100),
                         (100, 100, 100, 100),    # entrada 100,25
                         (100, 111, 89, 100)])    # toca stop 90 y objetivo 110: gana el stop
    sig = Signal("t", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    t = run(instruments, rules, {"MNQ": bars}, [sig]).trades.iloc[0]
    assert t.exit_reason == "stop"
    assert t.exit_price == 89.75                  # stop 90 menos 1 tick de deslizamiento


def test_gap_through_stop_fills_at_open(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100),
                         (100, 100, 100, 100),
                         (85, 86, 84, 85)])       # abre por debajo del stop
    sig = Signal("t", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    t = run(instruments, rules, {"MNQ": bars}, [sig]).trades.iloc[0]
    assert t.exit_price == 84.75


def test_short_trade(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100),
                         (100, 100, 100, 100),    # entrada corto 100 - 0,25 = 99,75
                         (99, 99, 89, 90)])       # toca objetivo 90
    sig = Signal("t", "MNQ", SHORT, ts(D, "09:30"), stop=110, target=90)
    t = run(instruments, rules, {"MNQ": bars}, [sig]).trades.iloc[0]
    assert t.entry_price == 99.75 and t.exit_reason == "target"
    assert t.pnl_gross == pytest.approx((99.75 - 90) * 2 * t.qty)


def test_forced_close(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100)] * 3, start="15:47")  # 15:47, 15:48, 15:49
    bars = pd.concat([bars, make_bars(D, [(105, 105, 105, 105)], start="15:50")])
    sig = Signal("t", "MNQ", LONG, ts(D, "15:47"), stop=90, target=120)
    t = run(instruments, rules, {"MNQ": bars}, [sig]).trades.iloc[0]
    assert t.exit_reason == "cierre_forzado"
    assert t.exit_time == ts(D, "15:50") and t.exit_price == 104.75


def test_no_entry_after_cutoff(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100)] * 3, start="15:49")
    sig = Signal("t", "MNQ", LONG, ts(D, "15:49"), stop=90, target=120)
    res = run(instruments, rules, {"MNQ": bars}, [sig])
    assert res.trades.empty
    assert res.rejected.reason.iloc[0] == "despues_de_hora_limite"


def test_opposite_positions_rejected(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100)] * 5)
    long_sig = Signal("a", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    short_sig = Signal("b", "MNQ", SHORT, ts(D, "09:31"), stop=110, target=90)
    res = run(instruments, rules, {"MNQ": bars}, [long_sig, short_sig])
    assert list(res.rejected.reason) == ["posicion_opuesta_correlacionada"]
    assert len(res.trades) == 1 and res.trades.iloc[0].strategy == "a"


def test_uncorrelated_opposite_allowed(instruments, rules):
    nq = make_bars(D, [(100, 100, 100, 100)] * 5)
    gc = make_bars(D, [(2000, 2000, 2000, 2000)] * 5)
    s1 = Signal("a", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    s2 = Signal("b", "MGC", SHORT, ts(D, "09:30"), stop=2010, target=1990)
    res = run(instruments, rules, {"MNQ": nq, "MGC": gc}, [s1, s2])
    assert res.rejected.empty and len(res.trades) == 2


def test_daily_budget_limits_risk(instruments, rules):
    # Tres pérdidas seguidas de ~150 $: tras dos, el presupuesto (500 $) solo deja ~200 $.
    ohlc = []
    for _ in range(3):
        ohlc += [(100, 100, 100, 100), (100, 100, 100, 100), (100, 100, 80, 80), (100, 100, 100, 100)]
    bars = make_bars(D, ohlc)
    sigs = [Signal(f"s{i}", "MNQ", LONG, bars.index[4 * i], stop=90, target=110) for i in range(3)]
    res = run(instruments, rules, {"MNQ": bars}, sigs)
    assert len(res.trades) == 3
    assert res.daily.pnl.iloc[0] >= -rules.daily_budget
    assert res.daily.min_intraday_pnl.iloc[0] >= -rules.daily_budget


def test_max_trades_per_day(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100), (100, 100, 100, 100), (100, 111, 100, 110)] * 4)
    sigs = [Signal(f"s{i}", "MNQ", LONG, bars.index[3 * i], stop=90, target=110) for i in range(4)]
    res = run(instruments, rules, {"MNQ": bars}, sigs)
    assert len(res.trades) == 3
    assert list(res.rejected.reason) == ["max_operaciones_dia"]


def test_bad_reward_risk_rejected(instruments, rules):
    # Objetivo de 2 puntos con stop de 30: Apex lo considera gestión de riesgo inaceptable.
    bars = make_bars(D, [(100, 100, 100, 100)] * 3)
    sig = Signal("t", "MNQ", LONG, ts(D, "09:30"), stop=70, target=102)
    res = run(instruments, rules, {"MNQ": bars}, [sig])
    assert res.rejected.reason.iloc[0] == "ratio_objetivo_stop_insuficiente"


def test_min_intraday_counts_unrealized(instruments, rules):
    bars = make_bars(D, [(100, 100, 100, 100),
                         (100, 100, 100, 100),    # entrada 100,25, 6 contratos
                         (100, 100, 95, 100),     # peor momento: mínimo 95
                         (100, 111, 100, 110)])   # objetivo
    sig = Signal("t", "MNQ", LONG, ts(D, "09:30"), stop=90, target=110)
    res = run(instruments, rules, {"MNQ": bars}, [sig])
    expected_worst = (95 - 100.25) * 2 * 6 - 1.5 * 6
    assert res.daily.min_intraday_pnl.iloc[0] == pytest.approx(expected_worst)
    assert res.daily.pnl.iloc[0] > 0
