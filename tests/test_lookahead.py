"""Automatic look-ahead tests on synthetic random walks (test-only data)."""
import numpy as np
import pandas as pd

from crt_xauusd.data import prepare
from crt_xauusd.execution import Market, build_trades
from crt_xauusd.signals import detect_all

from .conftest import synthetic_random_walk

KEY = ["setup_id", "direction", "conf_bar_time", "sweep_price", "volume_ratio"]


def _signals(raw, cfg):
    df, h4, _ = prepare(raw, cfg)
    return detect_all(df, h4, cfg, cfg["volume"]["base"])[0], df


def _loose(cfg):
    cfg["volume"]["base"]["threshold"] = 0.0  # more signals -> stronger test; rule logic unchanged
    return cfg


def test_signals_exist_in_fixture(cfg):
    sig, _ = _signals(synthetic_random_walk(end="2024-12-28"), _loose(cfg))
    assert len(sig) >= 10


def test_truncation_invariance(cfg):
    cfg = _loose(cfg)
    raw = synthetic_random_walk(end="2024-12-28")
    full, _ = _signals(raw, cfg)
    for cut in (0.35, 0.6, 0.85):
        T = raw["ts"].iloc[int(len(raw) * cut)]
        part, _ = _signals(raw[raw["ts"] < T].reset_index(drop=True), cfg)
        a = full[full["signal_time"] <= T][KEY].reset_index(drop=True)
        b = part[part["signal_time"] <= T][KEY].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_future_perturbation_does_not_change_past_signals(cfg):
    cfg = _loose(cfg)
    raw = synthetic_random_walk(end="2024-12-28")
    full, _ = _signals(raw, cfg)
    T = raw["ts"].iloc[len(raw) // 2]
    rng = np.random.default_rng(1)
    mod = raw.copy()
    fut = mod["ts"] >= T
    shift = rng.normal(0, 25, fut.sum())
    for c in ("open", "high", "low", "close"):
        mod.loc[fut, c] += shift
    mod.loc[fut, "volume"] = rng.permutation(mod.loc[fut, "volume"].to_numpy())
    pert, _ = _signals(mod, cfg)
    a = full[full["signal_time"] <= T][KEY].reset_index(drop=True)
    b = pert[pert["signal_time"] <= T][KEY].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_entry_strictly_after_signal_at_next_open(cfg):
    cfg = _loose(cfg)
    sig, df = _signals(synthetic_random_walk(end="2024-12-28"), cfg)
    t, _ = build_trades(sig, Market(df, cfg), cfg, "TP_1R")
    assert len(t) > 0
    assert (t["entry_time"] >= t["signal_time"]).all()
    assert (t["sweep_time"] < t["conf_bar_time"]).all()
    opens = df.set_index("ts")["open"]
    assert np.allclose(t["entry_price"].to_numpy(), opens.loc[t["entry_time"]].to_numpy())
    # reference 4H fully closed before the execution 4H begins
    assert (t["ref_start_ny"] + pd.Timedelta(hours=4) <= t["exec_start_ny"]).all()
    # the confirmation is exactly the bar after the sweep
    assert ((t["conf_bar_time"] - t["sweep_time"]) == pd.Timedelta(minutes=15)).all()


def test_volume_feature_is_causal(cfg):
    raw = synthetic_random_walk(end="2024-12-28")
    df, _, _ = prepare(raw, cfg)
    i = 500
    expected = raw["volume"].iloc[i] / raw["volume"].iloc[i - 20:i].mean()
    assert np.isclose(df["volume_ratio"].iloc[i], expected)
