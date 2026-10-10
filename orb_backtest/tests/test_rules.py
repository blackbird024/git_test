"""Pruebas de reglas (1-16, 20) con sesiones sintéticas de resultado conocido."""
from dataclasses import replace
from datetime import time

import numpy as np
import pandas as pd
import pytest

from orb_backtest.bars import Hourly
from orb_backtest.engine import run
from orb_backtest.structure import bias_at, find_pivots

from .conftest import LONG_SETUP, SHORT_SETUP, TZ, make_session, pivots


def one(cfg, sess, kind="alcista", **kw):
    tr, lg, eq = run([sess], pivots(kind, str(sess.date.date())), cfg, **kw)
    return tr, lg


# 1
def test_range_0930_1030(cfg):
    s = make_session(bars={"10:25": (100, 101.25, 98.5, 100), "10:30": (100, 103, 97, 100)})
    _, lg = one(cfg, s)
    assert lg[0].or_high == 101.25 and lg[0].or_low == 98.5          # la vela de 10:30 no forma parte del rango


# 2 y 20
def test_no_entry_before_1030(cfg):
    early = {"09:40": (100, 101.75, 100, 101.5), "09:45": (101.5, 101.5, 100.75, 101.5), "09:50": (101.5,) * 4}
    tr, lg = one(cfg, make_session(bars=early))
    assert tr == []
    tr, _ = one(cfg, make_session(bars=LONG_SETUP))
    assert pd.Timestamp(tr[0].entry_time).time() >= time(10, 35)


# 3 y 4
def _hourly(highs, lows, start="2024-03-04 00:00"):
    st = pd.date_range(start, periods=len(highs), freq="h", tz=TZ)
    return Hourly(st, st + pd.Timedelta(hours=1), np.array(highs, float), np.array(lows, float), np.full(len(highs), 12))


def test_pivot_confirmed_only_after_two_closed_bars():
    hb = _hourly([1, 2, 5, 3, 2, 1, 1], [0, 1, 4, 2, 1, 0, 0])
    p = find_pivots(hb)
    assert list(p.hi_val) == [5.0]
    assert p.hi_conf[0] == hb.start[2] + pd.Timedelta(hours=3)        # cierre de la vela i+2
    assert bias_at(p, p.hi_conf[0] - pd.Timedelta(minutes=1))[1]["n_highs"] == 0


def test_structure_has_no_lookahead():
    rng = np.random.default_rng(3)
    h = np.cumsum(rng.normal(0, 1, 200)) + 100
    l = h - 1
    hb = _hourly(h, l)
    t = hb.start[120] + pd.Timedelta(minutes=30)                       # dentro de una vela todavía abierta
    full = bias_at(find_pivots(hb), t)
    k = int(hb.close_time.searchsorted(t, side="right"))                # solo velas cerradas <= t
    trunc = bias_at(find_pivots(_hourly(h[:k], l[:k])), t)
    assert full == trunc
    h2 = h.copy(); h2[k:] += 50                                         # cambiar el futuro no cambia el sesgo
    assert bias_at(find_pivots(_hourly(h2, h2 - 1)), t) == full


def test_bias_rules():
    assert bias_at(pivots("alcista"), pd.Timestamp("2024-03-05 09:30", tz=TZ))[0] == "alcista"
    assert bias_at(pivots("bajista"), pd.Timestamp("2024-03-05 09:30", tz=TZ))[0] == "bajista"
    assert bias_at(pivots("neutral"), pd.Timestamp("2024-03-05 09:30", tz=TZ))[0] == "neutral"


# 5
def test_valid_long_and_short(cfg):
    tr, _ = one(cfg, make_session(bars=LONG_SETUP), "alcista")
    assert tr[0].side == "largo"
    tr, _ = one(cfg, make_session(bars=SHORT_SETUP), "bajista")
    assert tr[0].side == "corto"


def test_no_trade_against_structure_or_neutral(cfg):
    assert one(cfg, make_session(bars=LONG_SETUP), "bajista")[0] == []
    tr, lg = one(cfg, make_session(bars=LONG_SETUP), "neutral")
    assert tr == [] and lg[0].reason == "sesgo neutral"
    assert one(cfg, make_session(bars=LONG_SETUP), "neutral", use_filter=False)[0][0].side == "largo"


# 6
def test_breakout_without_retest_rejected(cfg):
    b = {"10:30": (100, 101.75, 100, 101.5), "10:35": (101.5, 103, 102, 102.5), "10:40": (102.5, 104, 102.5, 103.5),
         "10:45": (103.5, 105, 103.5, 104.5), "10:50": (104.5, 104.5, 100.75, 101.5)}   # retesteo en la 4.ª vela
    for k in ("10:55", "11:00"):
        b[k] = (101.5,) * 4
    tr, lg = one(cfg, make_session(bars=b))
    assert tr == [] and "sin ruptura" in lg[0].reason


# 7
@pytest.mark.parametrize("low,ok", [(100.5, True), (101.5, True), (100.25, False), (101.75, False)])
def test_retest_tolerance_two_ticks(cfg, low, ok):
    b = dict(LONG_SETUP)
    b.pop("10:45")                                                      # después, velas planas en el cierre
    b["10:40"] = (102.25, 102.25, low, 102.0)
    tr, _ = one(cfg, make_session(bars=b))
    assert bool(tr) == ok


# 8 y 9
def test_entry_stop_target(cfg):
    tr, _ = one(cfg, make_session(bars=LONG_SETUP))
    t = tr[0]
    assert t.entry_time.startswith("2024-03-05 10:45") and t.entry == 101.5
    assert t.stop == 100.75 - 0.5                                      # mínimo del retesteo − 2 ticks
    assert t.target == 101.5 + 2 * (101.5 - 100.25)


# 10
def test_position_size_respects_budget(cfg):
    tr, _ = one(cfg, make_session(bars=LONG_SETUP))
    t = tr[0]
    budget = 50_000 * 0.0025
    loss_pc = (101.5 - 100.25) * 2.0                                   # sin costes en esta fixture
    assert t.contracts == int(budget // loss_pc) and t.planned_risk_usd <= budget


# 11
def test_skip_when_one_contract_exceeds_budget(cfg):
    cfg.risk = replace(cfg.risk, initial_capital=500.0)                # presupuesto 1,25 $ < 2,50 $ por contrato
    tr, lg = one(cfg, make_session(bars=LONG_SETUP))
    assert tr == [] and lg[0].status == "descartada_riesgo"


# 12
def test_one_trade_per_session(cfg):
    b = dict(LONG_SETUP)
    b["10:50"] = (101.5, 101.5, 99.0, 99.5)                            # stop
    b.update({"11:30": (100, 101.75, 100, 101.5), "11:35": (101.5, 101.5, 100.75, 101.5), "11:40": (101.5,) * 4})
    tr, _ = one(cfg, make_session(bars=b))
    assert len(tr) == 1 and tr[0].exit_reason == "stop"


# 13
def test_forced_exit_1555(cfg):
    tr, _ = one(cfg, make_session(bars=LONG_SETUP))
    assert tr[0].exit_reason == "cierre_obligatorio" and tr[0].exit_time.startswith("2024-03-05 15:55")


# 14
def test_stop_first_when_both_in_same_bar(cfg):
    b = dict(LONG_SETUP)
    b["10:50"] = (101.5, 110.0, 99.0, 101.5)
    tr, _ = one(cfg, make_session(bars=b))
    assert tr[0].exit_reason == "stop" and tr[0].exit == 100.25


# 15
def test_gap_through_stop_fills_at_open(cfg):
    cfg.costs = replace(cfg.costs, slippage_ticks_per_side=1)
    b = dict(LONG_SETUP)
    b["10:50"] = (98.0, 98.5, 97.0, 98.0)
    tr, _ = one(cfg, make_session(bars=b))
    t = tr[0]
    assert t.exit_reason == "stop_hueco" and t.exit == 98.0 - 0.25 and t.entry == 101.5 + 0.25


def test_target_needs_one_tick_through(cfg):
    b = dict(LONG_SETUP)
    b["10:50"] = (101.5, 104.0, 101.5, 102.0)                          # toca el objetivo (104) sin superarlo
    b["10:55"] = (102.0, 104.25, 102.0, 103.0)                         # lo supera 1 tick → objetivo
    tr, _ = one(cfg, make_session(bars=b))
    assert tr[0].exit_reason == "objetivo" and tr[0].exit_time.startswith("2024-03-05 10:55") and tr[0].exit == 104.0


# 16
def test_costs_applied(cfg):
    cfg.costs = replace(cfg.costs, commission_per_side=0.62, slippage_ticks_per_side=1)
    b = dict(LONG_SETUP)
    b["10:50"] = (101.5, 101.5, 99.0, 99.5)
    tr, _ = one(cfg, make_session(bars=b))
    t = tr[0]
    n = t.contracts
    assert t.gross_usd == pytest.approx((t.stop - 101.5) * 2 * n)              # ideal: de la apertura al stop
    assert t.slippage_usd == pytest.approx(2 * 0.25 * 2 * n)                    # 1 tick en entrada y salida
    assert t.commission_usd == pytest.approx(2 * 0.62 * n)
    assert t.net_usd == pytest.approx(t.gross_usd - t.slippage_usd - t.commission_usd)


def test_entry_cutoff(cfg):
    late = {k.replace("10:", "14:").replace("14:45", "15:00").replace("14:40", "14:55").replace("14:35", "14:50")
            .replace("14:30", "14:45"): v for k, v in LONG_SETUP.items()}
    tr, lg = one(cfg, make_session(bars=late))
    assert tr == [] and lg[0].status == "descartada_hora"


def test_missing_range_bar_invalidates_session(cfg):
    tr, lg = one(cfg, make_session(bars=LONG_SETUP, drop=("09:55",)))
    assert tr == [] and lg[0].status == "invalida" and "rango incompleto" in lg[0].reason
