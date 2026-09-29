"""Pruebas de la reversión a la media y de la tendencia VWAP en MGC (casos calculados a mano)."""
import datetime as dt

import pandas as pd
import pytest

from src.strategies.intraday_vwap import MRConfig, VTConfig, _run_mr_day, _run_vt_day

D = "2024-03-04"
DATE = dt.date(2024, 3, 4)
TZ = "America/New_York"


def bars(rows, freq):
    idx = pd.date_range(f"{D} 09:30", periods=len(rows), freq=freq, tz=TZ)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    df["volume"] = 100.0
    return df


# ------------------------------------------------------------------ reversión a la media
MR = MRConfig()  # MNQ, desviación 0,5 ATR, 150 $, stop 1:1


def mr_day(spike_close):
    rows = [(100, 100, 100, 100)] * 78       # 9:30-15:55 en velas de 5 min, VWAP = 100
    rows[12] = (100, spike_close, 100, spike_close) if spike_close > 100 else (100, 100, spike_close, spike_close)
    rows[13] = (spike_close, spike_close, spike_close, spike_close)
    return bars(rows, "5min")


def test_mr_short_after_spike_above_vwap():
    day = mr_day(130)                         # vela de 10:30 cierra en 130 (> 100 + 0,5 x 40)
    t = _run_mr_day(DATE, day, 40.0, MR).trade
    assert t["direction"] == -1 and t["entry_time"] == pd.Timestamp(f"{D} 10:35", tz=TZ)
    assert t["entry"] == 129.75
    # VWAP al cierre de 10:30: 12 velas a 100 y una con precio típico (130 + 100 + 130) / 3 = 120.
    assert t["target"] == pytest.approx((100 * 12 + 120) / 13)
    reward = 129.75 - t["target"]
    assert t["stop"] == pytest.approx(129.75 + reward)   # 1:1


def test_mr_no_signal_inside_band_or_before_1030():
    assert _run_mr_day(DATE, mr_day(110), 40.0, MR).status == "sin_senal"     # 10 < 0,5 x 40
    early = bars([(100, 100, 100, 100)] * 5 + [(100, 150, 100, 150)] + [(150, 150, 150, 150)] * 72, "5min")
    t = _run_mr_day(DATE, early, 40.0, MR)
    assert t.status == "operada" and t.trade["entry_time"] >= pd.Timestamp(f"{D} 10:35", tz=TZ)


def test_fixed_contract_diagnostic_ignores_risk_limit():
    cfg = MR.variant(risk_usd=1, fixed_contracts=1)
    assert _run_mr_day(DATE, mr_day(130), 40.0, cfg).trade["qty"] == 1
    assert _run_mr_day(DATE, mr_day(130), 40.0, MR.variant(risk_usd=1)).status == "riesgo_de_1_contrato_excede_limite"


# ------------------------------------------------------------------ tendencia VWAP en MGC
VT = VTConfig(point_value=10.0, tick=0.1, first_signal="10:00", last_signal="14:30", stop_atr=0.4)


def test_vt_long_pullback():
    rows = [(100 + i * 0.1, 100.2 + i * 0.1, 99.9 + i * 0.1, 100.1 + i * 0.1) for i in range(390)]
    day = bars(rows, "1min")
    from src.strategies.intraday_vwap import session_vwap
    t_sig = pd.Timestamp(f"{D} 10:05", tz=TZ)
    v = session_vwap(day).loc[t_sig]
    day.loc[t_sig, ["open", "high", "low", "close"]] = [v + 1, v + 1.5, v - 0.1, v + 1]
    res = _run_vt_day(DATE, day, 20.0, VT)
    t = res.trade
    assert t["direction"] == 1 and t["entry_time"] == t_sig + pd.Timedelta(minutes=1)
    vwap_new = session_vwap(day).loc[t_sig]
    assert t["stop"] == pytest.approx(vwap_new - 0.4 * 20.0)
    assert t["target"] == pytest.approx(t["entry"] + 2 * (t["entry"] - t["stop"]))
