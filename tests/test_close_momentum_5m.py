"""Pruebas del momentum de cierre (velas de 1 minuto, casos calculados a mano)."""
import datetime as dt

import pandas as pd

from src.strategies.close_momentum_5m import CMConfig, _run_day
from tests.conftest import make_bars

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = CMConfig()


def day(morning_move, after_entry=None):
    ohlc = [(100.0, 100.0, 100.0, 100.0)] * 390                 # 9:30 ... 15:59
    ohlc[29] = (100.0, 100.0, 100.0, 100.0 + morning_move)       # vela de 9:59
    ohlc[360:] = [(200.0, 200.0, 200.0, 200.0)] * 30             # por la tarde el precio está en 200
    for i, bar in (after_entry or {}).items():
        ohlc[360 + i] = bar                                       # 360 = vela de 15:30
    return make_bars(D, ohlc).astype(float)


def test_long_after_up_morning_exit_1558():
    bars = day(+5, {0: (200.0, 200.0, 200.0, 200.0), 28: (210.0, 210.0, 210.0, 210.0)})
    t = _run_day(DATE, bars, 100.0, CFG).trade
    assert t["direction"] == 1
    assert t["entry"] == 200.25                                  # apertura 15:30 + 1 tick
    assert t["stop"] == 200.25 - 10.0                            # 10 % de un ATR de 100
    assert t["qty"] == 7                                         # floor(150 / (10 * 2))
    assert t["exit_time"] == pd.Timestamp(f"{D} 15:58", tz=TZ)
    assert t["exit"] == 210.0 and t["exit_reason"] == "tiempo"
    assert t["commission"] == 14.0
    assert t["pnl"] == (210.0 - 200.25) * 2 * 7 - 14.0


def test_short_emergency_stop():
    bars = day(-5, {0: (200.0, 200.0, 200.0, 200.0), 3: (200.0, 212.0, 199.0, 211.0)})
    t = _run_day(DATE, bars, 100.0, CFG).trade
    assert t["direction"] == -1 and t["entry"] == 199.75
    assert t["exit_reason"] == "stop" and t["exit"] == 209.75 + 0.25


def test_flat_morning_and_risk_limit():
    assert _run_day(DATE, day(0), 100.0, CFG).status == "manana_plana"
    assert _run_day(DATE, day(+5), 1000.0, CFG).status == "riesgo_de_1_contrato_excede_limite"  # 100 pts * 2 $ > 150 $
