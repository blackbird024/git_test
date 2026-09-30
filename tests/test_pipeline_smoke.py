"""End-to-end smoke test on SYNTHETIC data in a temp dir. Checks plumbing only."""
import json

from crt_xauusd import run as runner

from .conftest import synthetic_random_walk


def test_pipeline_runs_and_is_reproducible(tmp_path, cfg):
    raw = synthetic_random_walk(start="2023-01-01 18:00", end="2024-12-28", seed=3)
    csv = tmp_path / "SYN.csv"
    raw.assign(timestamp=raw["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")).drop(columns=["ts"]).to_csv(csv, index=False)
    (tmp_path / "SYN.meta.json").write_text(json.dumps({
        "source": "SYNTHETIC TEST FIXTURE", "broker": "none", "format": "generic", "timestamp_tz": "UTC",
        "price_side": "mid", "volume_type": "synthetic"}))
    cfg["volume"]["base"]["threshold"] = 1.0
    cfg["falsification"].update(n_permutations=20, n_volume_permutations=2)
    cfg["walk_forward"].update(is_months=6, oos_months=3, step_months=3)
    cfg_path = tmp_path / "CONFIG.json"
    cfg_path.write_text(json.dumps(cfg))
    outs = []
    for k in range(2):
        out = tmp_path / f"out{k}"
        assert runner.run(cfg_path, out, unlock_test=False, data_override=str(csv)) == 0
        outs.append(out)
    for f in ("CRT_XAUUSD_FINAL.md", "CRT_XAUUSD_TRADES.csv", "CRT_XAUUSD_MONTHLY.csv", "CRT_XAUUSD_YEARLY.csv",
              "CRT_XAUUSD_WALK_FORWARD.csv", "CRT_XAUUSD_MAE_MFE.csv", "RUN_MANIFEST.json", "charts/equity_curve.png"):
        assert (outs[0] / f).exists(), f
    a = (outs[0] / "CRT_XAUUSD_TRADES.csv").read_text()
    assert a == (outs[1] / "CRT_XAUUSD_TRADES.csv").read_text()
    assert "TEST" not in set(l.split(",")[0] for l in a.splitlines()[1:])  # TEST hidden while locked
    assert "LOCKED" in (outs[0] / "CRT_XAUUSD_FINAL.md").read_text()


def test_missing_dataset_reports_not_evaluated(tmp_path, cfg):
    cfg_path = tmp_path / "CONFIG.json"
    cfg["data"]["path"] = str(tmp_path / "nope.csv")
    cfg["data"]["metadata_path"] = str(tmp_path / "nope.meta.json")
    cfg_path.write_text(json.dumps(cfg))
    assert runner.run(cfg_path, tmp_path / "o", unlock_test=False) == 2
    assert "NOT EVALUATED" in (tmp_path / "o" / "CRT_XAUUSD_FINAL.md").read_text()
