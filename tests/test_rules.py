import numpy as np
import pandas as pd
import pytest

from crt_xauusd.data import _localize, prepare
from crt_xauusd.execution import Market, build_trades, simulate
from crt_xauusd.signals import confirm_engulfing, detect_all

from .conftest import scenario_frame

NY = "America/New_York"


def bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


# ---------------------------------------------------------------- pure engulfing rule
def test_owner_long_example_is_confirmation():
    ok, reasons, rec = confirm_engulfing(bar(2651.0, 2652.0, 2648.5, 2649.5), bar(2649.4, 2654.0, 2649.0, 2653.0), "long")
    assert ok and reasons == []
    assert rec["confirm_body"] == pytest.approx(3.6)


@pytest.mark.parametrize("sweep,conf,reason", [
    (bar(2649.0, 2652, 2648.5, 2651.0), bar(2650.9, 2654, 2650, 2653), "sweep_bar_not_bearish"),
    (bar(2651.0, 2652, 2648.5, 2649.5), bar(2653.0, 2654, 2649, 2649.4), "confirm_bar_not_bullish"),
    (bar(2651.0, 2652, 2648.5, 2649.5), bar(2649.6, 2654, 2649, 2653.0), "confirm_open_above_sweep_close"),
    (bar(2651.0, 2652, 2648.5, 2649.5), bar(2649.4, 2654, 2649, 2650.9), "confirm_close_below_sweep_open"),
])
def test_long_engulfing_failures(sweep, conf, reason):
    ok, reasons, _ = confirm_engulfing(sweep, conf, "long")
    assert not ok and reason in reasons


def test_short_engulfing_mirror():
    ok, _, _ = confirm_engulfing(bar(2649.0, 2651.5, 2648, 2650.5), bar(2650.6, 2651, 2646, 2647.0), "short")
    assert ok
    ok, r, _ = confirm_engulfing(bar(2649.0, 2651.5, 2648, 2650.5), bar(2650.6, 2651, 2646, 2649.5), "short")
    assert not ok and "confirm_close_above_sweep_open" in r


def test_engulfing_boundaries_are_inclusive():
    ok, _, _ = confirm_engulfing(bar(2651.0, 2652, 2648, 2649.5), bar(2649.5, 2652, 2649, 2651.0), "long")
    assert ok


# ---------------------------------------------------------------- full detector scenarios
EXAMPLE = {
    "02:15": (2651.0, 2652.0, 2648.5, 2649.5, 100),   # sweep of ref low 2650
    "02:30": (2649.4, 2654.0, 2649.0, 2653.0, 180),   # bullish engulfing, 1.8 x SMA20
}


def run_scenario(cfg, overrides, base=2651.0):
    df, h4, _ = prepare(scenario_frame(overrides, base_price=base), cfg)
    sig, skips, ev, setups = detect_all(df, h4, cfg, cfg["volume"]["base"], keep_events=True)
    return df, h4, sig, ev


def test_owner_example_end_to_end(cfg):
    df, h4, sig, _ = run_scenario(cfg, EXAMPLE)
    lon = sig[sig.kz == "london"]
    assert len(lon) == 1
    s = lon.iloc[0]
    assert s.direction == "long" and s.ref_low == 2650.0
    assert s.sweep_time == pd.Timestamp("2024-01-10 02:15", tz=NY).tz_convert("UTC")
    assert s.volume_ratio == pytest.approx(1.8)
    t, _ = build_trades(sig[sig.kz == "london"], Market(df, cfg), cfg, "TP_1R")
    tr = t.iloc[0]
    assert tr.entry_time == pd.Timestamp("2024-01-10 02:45", tz=NY).tz_convert("UTC")  # OPEN of bar #3
    assert tr.entry_time == tr.signal_time
    assert tr.entry_price == 2651.0
    assert tr.stop_price == pytest.approx(2648.5 - cfg["execution"]["stop_buffer_price"])
    assert tr.target_price == pytest.approx(tr.entry_price + tr.stop_distance)


def test_touching_level_is_not_a_sweep(cfg):
    ov = {"02:15": (2651.0, 2652.0, 2650.0, 2650.5, 100), "02:30": (2650.4, 2654.0, 2650.0, 2653.0, 180)}
    _, _, sig, _ = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 0


def test_no_waiting_window_third_bar_cannot_confirm(cfg):
    ov = {"02:15": (2651.0, 2652.0, 2648.5, 2649.5, 100),
          "02:30": (2649.5, 2650.0, 2649.0, 2649.8, 100),   # fails
          "02:45": (2649.4, 2654.0, 2649.0, 2653.0, 300)}   # would engulf -> must be ignored
    _, _, sig, ev = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 0
    lon = ev[(ev.kz == "london") & (ev.direction == "long")]
    assert lon.iloc[0]["event"] == "rejected"


def test_only_first_sweep_counts(cfg):
    ov = {"02:15": (2651.0, 2652.0, 2648.5, 2649.5, 100),
          "02:30": (2649.5, 2650.0, 2649.0, 2649.8, 100),   # first sweep invalidated
          "03:00": (2651.0, 2652.0, 2647.0, 2648.0, 100),   # second sweep
          "03:15": (2647.9, 2653.0, 2647.5, 2652.0, 400)}   # valid engulfing, but setup already dead
    _, _, sig, _ = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 0


def test_low_volume_invalidates(cfg):
    ov = dict(EXAMPLE); ov["02:30"] = (2649.4, 2654.0, 2649.0, 2653.0, 149)
    _, _, sig, ev = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 0
    assert "volume_below_threshold" in ev[(ev.kz == "london") & (ev.direction == "long")].iloc[0]["reasons"]


def test_volume_sma_excludes_current_bar(cfg):
    ov = dict(EXAMPLE); ov["02:30"] = (2649.4, 2654.0, 2649.0, 2653.0, 150)  # exactly 1.5 x prior mean 100
    df, _, sig, _ = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 1
    assert sig[sig.kz == "london"].iloc[0].volume_ratio == pytest.approx(1.5)


def test_confirmation_outside_kill_zone_invalid(cfg):
    ov = {"01:30": (2651.0, 2652.0, 2648.5, 2649.5, 100), "01:45": (2649.4, 2654.0, 2649.0, 2653.0, 300)}
    _, _, sig, ev = run_scenario(cfg, ov)
    assert (sig.kz == "london").sum() == 0
    assert "confirm_bar_outside_kill_zone" in ev[(ev.kz == "london") & (ev.direction == "long")].iloc[0]["reasons"]


def test_sweep_just_before_kz_confirmation_inside_is_valid(cfg):
    ov = {"01:45": (2651.0, 2652.0, 2648.5, 2649.5, 100), "02:00": (2649.4, 2654.0, 2649.0, 2653.0, 300)}
    _, _, sig, _ = run_scenario(cfg, ov)
    s = sig[sig.kz == "london"]
    assert len(s) == 1 and not s.iloc[0].sweep_in_kz


def test_ny_setup_uses_its_own_reference(cfg):
    # NY exec 05-09 -> ref 01-05 (lows 2650). Sweep 07:15, confirm 07:30
    ov = {"07:15": (2651.0, 2652.0, 2648.5, 2649.5, 100), "07:30": (2649.4, 2654.0, 2649.0, 2653.0, 300)}
    _, _, sig, _ = run_scenario(cfg, ov)
    s = sig[sig.kz == "ny"]
    assert len(s) == 1 and s.iloc[0].exec_start_ny == pd.Timestamp("2024-01-10 05:00")


# ---------------------------------------------------------------- time zones / DST
@pytest.mark.parametrize("day,utc_hour", [("2024-01-10", 7), ("2024-07-10", 6)])
def test_london_kz_follows_new_york_dst(cfg, day, utc_hour):
    df, h4, sig, _ = run_scenario_on_day(cfg, day)
    s = sig[sig.kz == "london"].iloc[0]
    assert s.conf_bar_time.hour == utc_hour and s.conf_bar_time.minute == 30


def run_scenario_on_day(cfg, day):
    df, h4, _ = prepare(scenario_frame({"02:15": EXAMPLE["02:15"], "02:30": EXAMPLE["02:30"]}, base_price=2651.0,
                                       day=day), cfg)
    return df, h4, detect_all(df, h4, cfg, cfg["volume"]["base"], keep_events=True)[0], None


def test_ny_plus_7_server_clock():
    naive = pd.Series(pd.to_datetime(["2024-07-10 09:00", "2024-01-10 09:00"]))
    utc = _localize(naive, "NY+7")
    assert list(utc.dt.hour) == [6, 7]  # 02:00 NY in summer (EDT) and winter (EST)


def test_h4_buckets_anchor_17_ny(cfg):
    df, h4, _ = prepare(scenario_frame({}, day="2024-07-10"), cfg)
    assert set(h4.index.hour) <= {17, 21, 1, 5, 9, 13}


# ---------------------------------------------------------------- execution
class _M:
    def __init__(self, o, h, l, c):
        self.o, self.h, self.l, self.c = map(np.array, (o, h, l, c))
        self.n = len(o)


def test_same_bar_sl_tp_assumes_stop():
    m = _M([100, 100], [100.5, 103], [99.5, 97], [100, 100])
    r = simulate(m, 0, "long", 100, 98, 102, 1)
    assert r["exit_reason"] == "stop" and r["exit_price"] == 98


def test_gap_through_stop_fills_at_open():
    m = _M([100, 96], [100.5, 96.5], [99.5, 95], [100, 96])
    r = simulate(m, 0, "long", 100, 98, 102, 1)
    assert r["exit_price"] == 96


def test_session_close_exit():
    m = _M([100, 100.5], [100.6, 101], [99.9, 100], [100.5, 100.8])
    r = simulate(m, 0, "long", 100, 98, 102, 1)
    assert r["exit_reason"] == "session_close" and r["exit_price"] == 100.8


# ---------------------------------------------------------------- futures contract roll
def test_contract_roll_inside_exec_4h_skips_setup(cfg):
    raw = scenario_frame(EXAMPLE, base_price=2651.0)
    raw["instrument_id"] = 1
    raw.loc[raw["ts"] >= pd.Timestamp("2024-01-10 03:00", tz=NY), "instrument_id"] = 2
    df, h4, _ = prepare(raw, cfg)
    sig, skips, _, _ = detect_all(df, h4, cfg, cfg["volume"]["base"])
    assert (sig.kz == "london").sum() == 0 if len(sig) else True
    assert "contract_roll_ref_or_exec_4h" in set(skips[skips.kz == "london"]["reason"])


def test_single_contract_still_signals(cfg):
    raw = scenario_frame(EXAMPLE, base_price=2651.0)
    raw["instrument_id"] = 7
    df, h4, _ = prepare(raw, cfg)
    sig, _, _, _ = detect_all(df, h4, cfg, cfg["volume"]["base"])
    assert (sig.kz == "london").sum() == 1
