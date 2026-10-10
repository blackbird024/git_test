"""Pruebas de datos (17, 18), reproducibilidad (19) e integración con el dataset sintético (20)."""
from dataclasses import replace
from datetime import time

import pandas as pd
import pytest

from orb_backtest import bars, data_io
from orb_backtest.pipeline import backtest
from orb_backtest.synthetic import synthetic_5m, to_csv

from .conftest import ROOT


def _csv(tmp_path, rows, name="d.csv"):
    p = tmp_path / name
    pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"]).to_csv(p, index=False)
    return p


# 17
def test_dst_sessions_use_new_york_clock(tmp_path, cfg):
    # 8 mar 2024 (EST, UTC-5) y 11 mar 2024 (EDT, UTC-4): 9:30 ET es 14:30Z y 13:30Z respectivamente
    df = synthetic_5m("2024-03-07", "2024-03-12")
    p = to_csv(df.tz_convert("UTC"), tmp_path / "utc.csv")              # el CSV va en UTC con "+00:00"
    d = data_io.read_csv(p)
    sess, _ = bars.sessions(d, cfg.strategy, 5)
    by = {str(s.date.date()): s for s in sess}
    for day in ("2024-03-08", "2024-03-11"):
        assert by[day].start[0].time() == time(9, 30) and by[day].start[-1].time() == time(15, 55)
        assert len(by[day].start) == 78
    assert by["2024-03-08"].start[0].tz_convert("UTC").hour == 14
    assert by["2024-03-11"].start[0].tz_convert("UTC").hour == 13


# 18
def test_naive_timestamps_rejected(tmp_path):
    p = _csv(tmp_path, [["2024-03-05 09:30:00", 1, 2, 0.5, 1]])
    with pytest.raises(data_io.DataError):
        data_io.read_csv(p)


def test_non_numeric_rejected(tmp_path):
    p = _csv(tmp_path, [["2024-03-05T09:30:00-05:00", "x", 2, 0.5, 1]])
    with pytest.raises(data_io.DataError):
        data_io.read_csv(p)


def test_validation_flags_duplicates_order_ohlc_and_gaps(tmp_path):
    rows = [["2024-03-05T09:30:00-05:00", 100, 101, 99, 100],
            ["2024-03-05T09:30:00-05:00", 100, 101, 99, 100],          # duplicada
            ["2024-03-05T09:40:00-05:00", 100, 99, 101, 100],          # OHLC imposible; falta 9:35
            ["2024-03-05T09:35:00-05:00", 100, 101, 99, 100]]          # fuera de orden
    v = data_io.validate(data_io.read_csv(_csv(tmp_path, rows)), 0.25, 5)
    assert not v.ok and v.duplicates == 1 and v.impossible_ohlc == 1 and v.out_of_order == 1
    assert v.rth_sessions_with_missing_bars == 1


def test_scale_and_grid_warnings(tmp_path):
    rows = [["2024-03-05T09:30:00-05:00", 100, 101, 99, 100], ["2024-03-05T09:35:00-05:00", 1000.1, 1000.1, 1000.1, 1000.1]]
    v = data_io.validate(data_io.read_csv(_csv(tmp_path, rows)), 0.25, 5)
    assert v.suspicious_jumps == 1 and v.off_grid_prices == 1


# 19 y 20
@pytest.fixture
def synth_cfg(tmp_path, cfg):
    p = to_csv(synthetic_5m("2024-01-01", "2024-04-30"), tmp_path / "s.csv")
    cfg.data_file = p
    cfg.output_dir = tmp_path / "out"
    cfg.bootstrap_samples = 200
    cfg.costs = replace(cfg.costs, commission_per_side=0.62, slippage_ticks_per_side=1)
    return cfg


def test_reproducible(synth_cfg):
    a = backtest(synth_cfg, write=False)
    b = backtest(synth_cfg, write=False)
    for k in a["results"]:
        pd.testing.assert_frame_equal(a["results"][k][0], b["results"][k][0])
    pd.testing.assert_frame_equal(a["summary"], b["summary"])


def test_integration_hours_and_invariants(synth_cfg):
    out = backtest(synth_cfg, write=True)
    t = out["results"]["sin_filtro_1h"][0]
    assert len(t) > 0
    e = pd.to_datetime(t["entry_time"].str[:19])
    x = pd.to_datetime(t["exit_time"].str[:19])
    assert (e.dt.time >= time(10, 35)).all() and (e.dt.time < time(15, 0)).all()
    assert (x.dt.time <= time(15, 55)).all() and (x >= e).all()
    assert t.groupby("session").size().max() == 1
    long_ = t.side == "largo"
    assert (t.loc[long_, "stop"] < t.loc[long_, "entry"]).all() and (t.loc[~long_, "stop"] > t.loc[~long_, "entry"]).all()
    assert (t["planned_risk_usd"] <= t["risk_budget"] + 1e-9).all()
    assert (out["dir"] / "INFORME.md").exists()
