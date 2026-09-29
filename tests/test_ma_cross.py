"""Pruebas del cruce de medias con filtro ADX (señales colocadas a mano en un día inventado)."""
import datetime as dt

import numpy as np
import pandas as pd

from src.strategies.ma_cross import MAConfig, _run_day, adx

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = MAConfig(fixed_contracts=1)   # MNQ, 1 contrato, stop 0,25 ATR, deslizamiento 1 tick en todo


def day(crosses: dict, ok=True, price=100.0):
    n = 78                                                       # 9:30 ... 15:55
    idx = pd.date_range(f"{D} 09:30", periods=n, freq="5min", tz=TZ)
    df = pd.DataFrame({"open": price, "high": price, "low": price, "close": price, "volume": 1.0}, index=idx)
    df["cross"] = 0
    for i, c in crosses.items():
        df.iloc[i, df.columns.get_loc("cross")] = c
    df["ok_filter"] = ok
    return df


def test_long_then_reverse_on_opposite_cross():
    # 10:00 (vela 6) cruce al alza; 11:00 (vela 18) cruce a la baja -> sale y gira a corto.
    res = _run_day(DATE, day({6: 1, 18: -1}), 40.0, CFG)
    status, (t1, _), (t2, _) = res
    assert status == "operada"
    assert t1["direction"] == 1 and t1["entry_time"] == pd.Timestamp(f"{D} 10:05", tz=TZ)
    assert t1["exit_reason"] == "cruce_contrario" and t1["exit_time"] == pd.Timestamp(f"{D} 11:05", tz=TZ)
    assert t1["entry"] == 100.25 and t1["exit"] == 99.75       # 1 tick en contra al entrar y al salir
    assert t2["direction"] == -1 and t2["entry_time"] == pd.Timestamp(f"{D} 11:05", tz=TZ)
    assert t2["exit_reason"] == "tiempo" and t2["exit_time"] == pd.Timestamp(f"{D} 15:45", tz=TZ)


def test_range_filter_blocks_entries():
    assert _run_day(DATE, day({6: 1}, ok=False), 40.0, CFG)[0] == "cruces_en_rango_filtrados"


def test_signals_outside_window_ignored_and_max_trades():
    assert _run_day(DATE, day({2: 1}), 40.0, CFG)[0] == "sin_senal"          # 9:40, antes de las 10:00
    many = {6 + 2 * k: (1 if k % 2 == 0 else -1) for k in range(10)}
    res = _run_day(DATE, day(many), 40.0, CFG)
    assert len(res) - 1 == 3                                                  # tope de 3 operaciones


def test_emergency_stop():
    df = day({6: 1})
    df.iloc[8, df.columns.get_loc("low")] = 80.0                              # cae por debajo del stop (100,25 - 10)
    t = _run_day(DATE, df, 40.0, CFG)[1][0]
    assert t["exit_reason"] == "stop" and t["exit"] == 90.25 - 0.25


def test_adx_high_in_trend_low_in_range():
    idx = pd.date_range(f"{D} 09:30", periods=300, freq="5min", tz=TZ)
    trend = pd.DataFrame({"close": np.arange(300.0)}, index=idx)
    trend["high"], trend["low"] = trend.close + 0.5, trend.close - 0.5
    rng = pd.DataFrame({"close": 100 + np.tile([0.0, 1.0], 150)}, index=idx)
    rng["high"], rng["low"] = rng.close + 0.5, rng.close - 0.5
    assert adx(trend, 14).iloc[-1] > 40 and adx(rng, 14).iloc[-1] < 20


def test_short_day_without_1545_bar_closes_at_last_bar():
    df = day({6: 1}).iloc[:40]                                               # el día acaba a las 12:50
    res = _run_day(DATE, df, 40.0, CFG)
    assert len(res) == 2 and res[1][0]["exit_reason"] == "tiempo"
