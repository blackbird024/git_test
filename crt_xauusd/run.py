"""Single reproducible entry point.

    python -m crt_xauusd.run                 # TRAIN + VALIDATION only (TEST stays hidden)
    python -m crt_xauusd.run --unlock-test   # one-way door: evaluates TEST and records it

Without a dataset it writes reports/CRT_XAUUSD_FINAL.md with status NOT EVALUATED and exits 2.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import analysis, falsification, report
from .config import ROOT, build_manifest, config_hash, load_config
from .data import DataMissingError, load_metadata, prepare, read_raw
from .execution import Market, all_take_profits, build_trades, combine_groups
from .metrics import holm, summarize
from .signals import detect_all

GROUPS = ["LONDON", "NY", "LONDON+NY"]


def _visible(t: pd.DataFrame, unlocked: bool) -> pd.DataFrame:
    if len(t) == 0 or unlocked:
        return t
    return t[t["split"] != "TEST"]


def _trainval(t):
    return t[t["split"].isin(["TRAIN", "VALIDATION"])] if len(t) else t


def run(cfg_path: Path, out: Path, unlock_test: bool, data_override: str | None = None) -> int:
    cfg = load_config(cfg_path)
    out.mkdir(parents=True, exist_ok=True)
    data_path = Path(data_override) if data_override else ROOT / cfg["data"]["path"]
    meta_path = data_path.with_suffix(".meta.json") if data_override else ROOT / cfg["data"]["metadata_path"]
    try:
        meta = load_metadata(meta_path)
        raw = read_raw(data_path, meta)
    except DataMissingError as e:
        report.write_not_evaluated(out, cfg, str(e))
        print(f"NOT EVALUATED: {e}", file=sys.stderr)
        return 2

    rng = np.random.default_rng(cfg["seed"])
    df, h4, audit = prepare(raw, cfg)
    audit["metadata"] = meta
    bounds = analysis.split_boundaries(df, cfg)
    manifest = build_manifest(cfg, data_path)
    manifest["splits_utc"] = {k: [str(a), str(b)] for k, (a, b) in bounds.items()}
    manifest["test_unlocked"] = unlock_test

    if unlock_test:
        lock = out / "TEST_UNLOCK.json"
        prev = json.loads(lock.read_text()) if lock.exists() else None
        if prev and prev["config_sha256"] != config_hash(cfg):
            manifest["test_contamination_warning"] = (
                "TEST was previously unlocked under a DIFFERENT config. TEST is no longer a clean hold-out.")
        if not prev:
            lock.write_text(json.dumps({"unlocked_at_utc": datetime.now(timezone.utc).isoformat(),
                                        "config_sha256": config_hash(cfg), "git_commit": manifest["git_commit"]},
                                       indent=2))
        manifest["test_unlock_record"] = json.loads(lock.read_text())

    base_var = cfg["volume"]["base"]
    base_tp = cfg["execution"]["base_tp"]
    m = Market(df, cfg)

    # ---------------- BASE
    sig, skips, events, setups = detect_all(df, h4, cfg, base_var, keep_events=True)
    trades, exec_skips = build_trades(sig, m, cfg, base_tp)
    if len(trades):
        trades = analysis.assign_split(trades, bounds)
    groups = {g: _visible(t, unlock_test) for g, t in combine_groups(trades).items()}
    splits = ["TRAIN", "VALIDATION"] + (["TEST"] if unlock_test else [])

    res = {"audit": audit, "manifest": manifest, "bounds": bounds, "unlocked": unlock_test,
           "n_setups": int(len(setups)), "n_signals": int(len(sig))}
    res["setup_skips"] = skips["reason"].value_counts().to_dict() if len(skips) else {}
    res["exec_skips"] = exec_skips["reason"].value_counts().to_dict() if len(exec_skips) else {}
    if len(events):
        ev = events[events["event"].isin(["rejected", "invalid"])]
        res["rejection_reasons"] = ev["reasons"].str.split(";").explode().value_counts().to_dict()
        res["event_counts"] = events["event"].value_counts().to_dict()

    tbl = {}
    for g, t in groups.items():
        for sp in splits:
            tbl[(g, sp)] = summarize(t[t["split"] == sp] if len(t) else t)
        tbl[(g, "TRAIN+VALIDATION")] = summarize(_trainval(t))
    res["summary"] = tbl
    res["holm"] = holm({g: tbl[(g, "TRAIN+VALIDATION")].get("p_value_one_sided", np.nan) for g in GROUPS},
                       cfg["success_criteria"]["holm_alpha"])

    # ---------------- robustness (TRAIN+VALIDATION)
    rob = []

    def add(kind, level, tr):
        tr = analysis.assign_split(tr, bounds) if len(tr) else tr
        for g, t in combine_groups(tr).items():
            s = summarize(_trainval(t))
            rob.append({"kind": kind, "level": level, "group": g, **{k: s.get(k) for k in (
                "trades", "expectancy_R", "profit_factor", "win_rate", "total_R", "max_drawdown_R")}})

    for mult in cfg["costs"]["multipliers"]:
        add("cost_multiplier", f"{mult}x", build_trades(sig, m, cfg, base_tp, cost_mult=mult)[0])
    for u in cfg["costs"]["slippage_units"]:
        add("slippage_per_side", f"{u} x {cfg['costs']['slippage_unit_price']}",
            build_trades(sig, m, cfg, base_tp, slippage_per_side=u * cfg["costs"]["slippage_unit_price"])[0])
    for d in cfg["robustness"]["entry_delay_bars"]:
        add("entry_delay_bars", str(d), build_trades(sig, m, cfg, base_tp, delay=d)[0])
    for tp in all_take_profits(cfg):
        add("take_profit", tp, build_trades(sig, m, cfg, tp)[0])
    for name, var in cfg["volume"]["sensitivity"].items():
        s2, _, _, _ = detect_all(df, h4, cfg, var)
        add("volume_definition", name, build_trades(s2, m, cfg, base_tp)[0])
    add("volume_definition", "base_ratio_1.5", trades.drop(columns=["split"]) if len(trades) else trades)
    res["robustness"] = pd.DataFrame(rob)

    # ---------------- walk-forward (stability of the frozen rule)
    tv_span = (bounds["TRAIN"][0], bounds["VALIDATION"][1])
    full_span = (bounds["TRAIN"][0], bounds["TEST"][1])
    wf = analysis.walk_forward({g: _trainval(t) for g, t in groups.items()}, tv_span, cfg)
    wf["span"] = "TRAIN+VALIDATION"
    if unlock_test:
        wf2 = analysis.walk_forward(groups, full_span, cfg)
        wf2["span"] = "FULL (TEST unlocked)"
        wf = pd.concat([wf, wf2], ignore_index=True)
    res["walk_forward"] = wf

    # ---------------- falsification (TRAIN+VALIDATION)
    res["falsification"] = {g: falsification.run_all(_trainval(groups[g]), df, h4, setups, cfg, tv_span, g, rng)
                            for g in GROUPS}

    # ---------------- regimes (descriptive, never filters)
    vr, er = analysis.regime_features(df, h4, cfg)
    groups = {g: analysis.add_regimes(t, vr, er, cfg) for g, t in groups.items()}
    res["regimes"] = {g: analysis.regime_tables(_trainval(t)) for g, t in groups.items()}

    # ---------------- criteria & verdict
    res["criteria"] = {g: evaluate_criteria(g, res, groups[g], cfg) for g in GROUPS}
    res["verdict"] = verdict(res["criteria"], unlock_test)

    report.write_all(out, cfg, res, groups, sig, events, exec_skips)
    print(f"VERDICT: {res['verdict']['verdict']}")
    return 0


def evaluate_criteria(g: str, res: dict, t: pd.DataFrame, cfg: dict) -> dict:
    sc = cfg["success_criteria"]
    tv = res["summary"][(g, "TRAIN+VALIDATION")]
    tr, va = res["summary"][(g, "TRAIN")], res["summary"][(g, "VALIDATION")]
    rob = res["robustness"]

    def rob_exp(kind, level):
        r = rob[(rob.kind == kind) & (rob.level == level) & (rob.group == g)]
        return float(r["expectancy_R"].iloc[0]) if len(r) and r["expectancy_R"].notna().iloc[0] else np.nan

    wf = res["walk_forward"]
    wf = wf[(wf.group == g) & (wf.span == "TRAIN+VALIDATION") & (wf.oos_trades > 0)] if len(wf) else wf
    fz = res["falsification"][g]
    alpha = sc["randomization_alpha"]
    rand_ok = {k: (fz.get(k, {}).get("p_value", 1.0) < alpha) for k in (
        "random_direction", "time_randomization", "random_entry", "volume_permutation", "randomized_sweep")}
    trim_key = f"expectancy_R_without_top{int(sc['outlier_trim_top_frac'] * 100)}pct"
    c = {
        "enough_trades_trainval": tv.get("trades", 0) >= sc["min_trades_trainval"],
        "positive_expectancy_TRAIN": tr.get("expectancy_R", -1) > 0,
        "positive_expectancy_VALIDATION": va.get("expectancy_R", -1) > 0,
        "holm_significant_trainval": bool(res["holm"][g]["reject_H0"]),
        "survives_cost_multiplier": rob_exp("cost_multiplier", f"{sc['cost_multiplier_must_survive']}x") > 0,
        "walk_forward_stable": (len(wf) > 0 and (wf["oos_expectancy_R"] > 0).mean() >= sc["wf_min_positive_window_frac"]),
        "yearly_stable": tv.get("pct_positive_years", 0) >= sc["min_positive_year_frac"],
        "neighbour_params_positive": all(x > 0 for x in (
            rob_exp("volume_definition", "ratio_1.3"), rob_exp("volume_definition", "ratio_1.7"),
            rob_exp("take_profit", "TP_1.5R"), rob_exp("entry_delay_bars", "1"))),
        "not_outlier_dependent": (tv.get(trim_key) or -1) > 0,
        **{f"beats_null_{k}": v for k, v in rand_ok.items()},
    }
    if res["unlocked"]:
        te = res["summary"][(g, "TEST")]
        c["TEST_positive"] = te.get("expectancy_R", -1) > 0 and te.get("trades", 0) >= sc["min_trades_test"]
    else:
        c["TEST_positive"] = None  # locked
    c["economic_coherence"] = None  # judged in the written report, not automatable
    return c


def verdict(criteria: dict, unlocked: bool) -> dict:
    out = {}
    for g, c in criteria.items():
        auto = {k: v for k, v in c.items() if v is not None}
        passed = sum(bool(v) for v in auto.values())
        nulls_beaten = sum(bool(v) for k, v in c.items() if k.startswith("beats_null_"))
        # PROMISING needs real evidence, not just positive point estimates: a pure random walk passes
        # "TRAIN>0, VALIDATION>0, 2x costs>0" by chance often enough (verified in development).
        core = (c["enough_trades_trainval"] and c["positive_expectancy_TRAIN"] and c["positive_expectancy_VALIDATION"]
                and c["survives_cost_multiplier"] and c["holm_significant_trainval"] and nulls_beaten >= 3)
        if all(auto.values()) and unlocked:
            v = "ROBUST EDGE"
        elif core:
            v = "PROMISING BUT INSUFFICIENT"
        else:
            v = "NO ROBUST EDGE"
        out[g] = {"verdict": v, "passed": passed, "evaluated": len(auto)}
    order = ["NO ROBUST EDGE", "PROMISING BUT INSUFFICIENT", "ROBUST EDGE"]
    best = max((o["verdict"] for o in out.values()), key=order.index)
    return {"verdict": best, "by_group": out,
            "note": "Overall verdict = best group verdict; every group is reported and Holm-corrected over 3 groups."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "CONFIG.json"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    ap.add_argument("--data", default=None, help="override dataset path (sidecar <name>.meta.json required)")
    ap.add_argument("--unlock-test", action="store_true")
    a = ap.parse_args(argv)
    return run(Path(a.config), Path(a.out), a.unlock_test, a.data)


if __name__ == "__main__":
    raise SystemExit(main())
