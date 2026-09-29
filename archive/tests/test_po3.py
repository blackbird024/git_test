"""Pruebas del Power of Three (casos inventados calculados a mano, velas de 5 min desde las 00:00)."""
import datetime as dt

import pandas as pd

from src.strategies.po3 import PO3Config, _run_day

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = PO3Config()  # MNQ, entrada "sesgo", objetivo 2R, 250 $


def day(manip_high=None, manip_low=None, after=None):
    """Noche plana en 100 (rango asiático 99-101). Barrida opcional entre 3:00 y 5:00."""
    n = 16 * 12                                                 # 00:00 ... 15:55
    rows = [(100.0, 101.0, 99.0, 100.0)] * n
    if manip_high:
        rows[40] = (100.0, manip_high, 99.5, 100.0)             # 3:20
    if manip_low:
        rows[44] = (100.0, 100.5, manip_low, 100.0)             # 3:40
    for i, bar in (after or {}).items():
        rows[i] = bar
    idx = pd.date_range(f"{D} 00:00", periods=n, freq="5min", tz=TZ)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100.0
    return df


def test_sweep_high_gives_short_at_0800():
    t = _run_day(DATE, day(manip_high=110.0), CFG).trade
    assert t["direction"] == -1
    assert t["entry_time"] == pd.Timestamp(f"{D} 08:00", tz=TZ) and t["entry"] == 99.75
    assert t["stop"] == 110.25                                  # extremo de la barrida + 1 tick
    dist = 110.25 - 99.75
    assert t["qty"] == 10                                       # 250 / (10,5 x 2) = 11,9 -> tope de 10
    assert t["target"] == 99.75 - 2 * dist


def test_no_trade_if_both_or_no_sweep():
    assert _run_day(DATE, day(), CFG).status == "sin_barrida"
    assert _run_day(DATE, day(manip_high=105.0, manip_low=95.0), CFG).status == "barrida_ambos_lados"


def test_confirmation_entry_waits_for_bearish_close_inside_range():
    # 8:00 y 8:05 cierran por encima del máximo asiático (101); la de 8:10 cierra dentro y bajista.
    after = {96: (102.0, 103.0, 101.5, 102.5), 97: (102.5, 103.0, 101.5, 102.0), 98: (102.0, 102.0, 100.0, 100.5)}
    t = _run_day(DATE, day(manip_high=110.0, after=after), CFG.variant(entry_mode="confirmacion")).trade
    assert t["entry_time"] == pd.Timestamp(f"{D} 08:15", tz=TZ)
    assert t["stop"] == 110.25


def test_long_after_sweep_low():
    t = _run_day(DATE, day(manip_low=90.0), CFG.variant(target_r=None)).trade
    assert t["direction"] == 1 and t["stop"] == 89.75 and t["target"] is None
    assert t["exit_reason"] == "tiempo"
