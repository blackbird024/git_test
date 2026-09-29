"""Pruebas del setup ICT de oro (día inventado en hora de Italia, calculado a mano).

Asia (06:00-08:50) plana: máximo 2001, mínimo 1999. Día anterior: máximo 2003, mínimo 1990 (50 % = 1996,5).
Sesgo bajista. MGC: 1 $ de precio = 10 $ por contrato, tick 0,10.
"""
import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest

from src.strategies.gold_ict import GoldICTConfig, run_day

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "Europe/Rome"
CFG = GoldICTConfig()
CTX = SimpleNamespace(bias=-1.0, prev_high=2003.0, prev_low=1990.0, mid=1996.5)


def day(window_bars: dict, after=1999.0):
    rows = [(2000.0, 2001.0, 1999.0, 2000.0)] * 170            # 06:00 ... 08:49
    rows += [(after, after + 0.05, after - 0.05, after)] * 130   # 08:50 ... 10:59
    for i, bar in window_bars.items():
        rows[170 + i] = bar
    idx = pd.date_range(f"{D} 06:00", periods=300, freq="1min", tz=TZ)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


# Subida que barre Asia y el día anterior dejando un FVG alcista (8:50-8:52), y cierre por debajo del FVG a las 8:54.
SWEEP_IFVG = {
    0: (2000.0, 2001.5, 1999.8, 2001.2),
    1: (2001.2, 2002.0, 2001.0, 2001.8),
    2: (2001.8, 2003.0, 2002.2, 2002.8),   # FVG: mínimo 2002,2 > máximo de 8:50 (2001,5)
    3: (2002.8, 2002.9, 2001.6, 2001.8),
    4: (2001.8, 2001.9, 2001.0, 2001.2),   # cierra por debajo de 2001,5 -> IFVG
    5: (2001.2, 2001.3, 2000.5, 2000.6),   # entrada en su apertura
    6: (2000.6, 2000.7, 1998.9, 1999.0),   # toca el mínimo de Asia (objetivo)
}


def test_short_ifvg_to_asia_low():
    status, found = run_day(DATE, day(SWEEP_IFVG), CTX, CFG)
    t, _ = found[0]
    assert status == "operada" and t["tipo_entrada"] == "IFVG"
    assert t["entry_time"] == pd.Timestamp(f"{D} 08:55", tz=TZ)
    assert t["entry"] == pytest.approx(2001.1)                   # 2001,2 - 1 tick
    assert t["stop"] == pytest.approx(2004.5)                    # 2003 + 1,5
    assert t["target"] == pytest.approx(1999.0)                  # Asia (2,1) queda antes que 2R (6,8)
    assert t["qty"] == 7                                         # floor(250 / (3,4 x 10))
    assert t["exit_reason"] == "objetivo"
    assert t["pnl"] == pytest.approx((2001.1 - 1999.0) * 10 * 7 - 14)


def test_breaker_when_no_fvg():
    no_gap = {0: (2000.0, 2001.5, 1999.8, 2001.2), 1: (2001.2, 2002.0, 2001.0, 2001.8),
              2: (2001.8, 2003.0, 2001.4, 2002.8), 3: (2002.8, 2002.9, 2001.6, 2001.8),
              4: (2001.8, 2001.9, 2001.0, 2001.2)}             # 8:54 cierra bajo el mínimo de 8:52 (2001,4)
    t = run_day(DATE, day(no_gap), CTX, CFG)[1][0][0]
    assert t["tipo_entrada"] == "breaker" and t["entry_time"] == pd.Timestamp(f"{D} 08:55", tz=TZ)


def test_no_trade_when_bias_disagrees_or_out_of_zone():
    assert run_day(DATE, day(SWEEP_IFVG), SimpleNamespace(**{**CTX.__dict__, "bias": 0.0}), CFG)[0] == "sesgo_contradictorio"
    discount = SimpleNamespace(**{**CTX.__dict__, "mid": 2010.0})   # todo el barrido queda en discount
    assert run_day(DATE, day(SWEEP_IFVG), discount, CFG)[0] == "sin_setup"


def test_first_stop_ends_the_day():
    bars = dict(SWEEP_IFVG)
    bars[6] = (2000.6, 2005.0, 2000.5, 2004.8)                   # sube al stop
    bars[80] = (1999.0, 2004.0, 1999.0, 2003.5)                  # otro barrido en la ventana 2 (10:10)
    status, found = run_day(DATE, day(bars), CTX, CFG)
    assert len(found) == 1 and found[0][0]["exit_reason"] == "stop"


def test_smt_requires_silver_divergence():
    cfg = CFG.variant(smt=True)
    silver_ctx = SimpleNamespace(prev_high=25.0, prev_low=23.0)
    s_idx = pd.date_range(f"{D} 06:00", periods=300, freq="1min", tz=TZ)
    flat = pd.DataFrame({"open": 24.0, "high": 24.1, "low": 23.9, "close": 24.0}, index=s_idx)
    assert run_day(DATE, day(SWEEP_IFVG), CTX, cfg, (flat, silver_ctx))[0] == "operada"     # plata no barre
    breaks = flat.copy()
    breaks.loc[f"{D} 08:51", "high"] = 26.0                      # la plata también supera su máximo
    assert run_day(DATE, day(SWEEP_IFVG), CTX, cfg, (breaks, silver_ctx))[0] == "sin_setup"
