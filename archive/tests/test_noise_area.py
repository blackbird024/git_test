"""Pruebas de la estrategia de zona de ruido (día inventado, sigma fija del 1 %).

Apertura 100 y cierre anterior 100 -> banda superior 101, inferior 99 en todos los minutos.
MNQ, 1 contrato: 1 punto = 2 $, tick 0,25, comisión 1 $ por lado.
"""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategies.noise_area import NoiseConfig, run_day

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = NoiseConfig(fixed_contracts=1)
SIGMA = pd.Series(0.01, index=range(390))


def day(prices: dict, base=100.0):
    """390 velas de 1 min. `prices` = {minuto: precio} desde ese minuto en adelante (escalones)."""
    close = np.full(390, base)
    for m in sorted(prices):
        close[m:] = prices[m]
    idx = pd.date_range(f"{D} 09:30", periods=390, freq="1min", tz=TZ)
    df = pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close}, index=idx)
    df["volume"] = 1.0
    df["minute"] = range(390)
    return df


def test_long_breakout_held_until_close():
    df = day({20: 102.0})                    # a las 9:50 sale de la zona de ruido por arriba
    (t, _), = run_day(DATE, df, 100.0, 100.0, SIGMA, 1, 0.01, CFG)
    assert t["direction"] == 1
    assert t["entry_time"] == pd.Timestamp(f"{D} 10:00", tz=TZ)      # primer chequeo
    assert t["entry"] == 102.25 and t["exit_reason"] == "cierre" and t["exit"] == 101.75


def test_no_trade_inside_noise_area():
    assert run_day(DATE, day({20: 100.8}), 100.0, 100.0, SIGMA, 1, 0.01, CFG) == []


def test_trailing_exit_and_flip_at_check():
    # Largo a las 10:00; a las 10:29 cae a 98 (< VWAP y < banda inferior) -> en el chequeo de 10:30 sale y gira.
    df = day({20: 102.0, 59: 98.0})
    res = run_day(DATE, df, 100.0, 100.0, SIGMA, 1, 0.01, CFG)
    (t1, _), (t2, _) = res
    assert t1["exit_reason"] == "trailing" and t1["exit_time"] == pd.Timestamp(f"{D} 10:30", tz=TZ)
    assert t1["exit"] == 97.75                                        # apertura 98 - 1 tick
    assert t2["direction"] == -1 and t2["entry"] == 97.75


def test_hard_stop_between_checks():
    # Largo a las 10:00 (stop = max(101, VWAP)); a las 10:10 cae a 100,5 entre chequeos.
    df = day({20: 102.0, 40: 100.5, 45: 102.0})
    soft = run_day(DATE, df, 100.0, 100.0, SIGMA, 1, 0.01, CFG)
    hard = run_day(DATE, df, 100.0, 100.0, SIGMA, 1, 0.01, CFG.variant(hard_stop=True))
    assert soft[0][0]["exit_reason"] == "cierre"                     # como el estudio: no mira entre chequeos
    t = hard[0][0]
    assert t["exit_reason"] == "stop_duro" and t["exit_time"] == pd.Timestamp(f"{D} 10:10", tz=TZ)
    assert t["exit"] == pytest.approx(100.5 - 0.25)                  # hueco bajo el stop: apertura - 1 tick
