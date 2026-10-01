"""Pre-registered funnel (docs/GENERATOR_PREREG.md).

    python -m strategy_gen.search stageA      # real gold: search -> robustness -> VALIDATION -> frozen list
    python -m strategy_gen.search nulls       # same funnel (+ their own 'TEST') on 3 shuffled series
    python -m strategy_gen.search stageB      # real gold TEST, only on the committed frozen list

Stage A never receives TEST bars: the frame is cut at the VALIDATION end before any feature is computed.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy import stats as st

from .backtest import Engine, stats
from .data import ROOT, load_h1, shuffled_null, splits
from .rules import Strategy, neighbours, random_strategy

OUT = ROOT / "reports" / "generator"
N_STRATS, SEED, NULL_SEEDS = 50_000, 20261001, (1, 2, 3)
MAX_FROZEN = 50


def generate(n=N_STRATS, seed=SEED) -> list[Strategy]:
    rng = np.random.default_rng(seed)
    seen, out = set(), []
    while len(out) < n:
        s = random_strategy(rng)
        if s.key() not in seen:
            seen.add(s.key()); out.append(s)
    return out


def _window(t, a, b):
    if len(t) == 0:
        return t
    et = pd.to_datetime(t["entry_time"], utc=True)
    return t[(et >= a) & (et < b)]


def deflated_sharpe(sr_best, n_trades, skew, kurt, sr_var, n_trials) -> float:
    g = 0.5772156649
    sr0 = np.sqrt(sr_var) * ((1 - g) * st.norm.ppf(1 - 1 / n_trials) + g * st.norm.ppf(1 - 1 / (n_trials * np.e)))
    den = np.sqrt(1 - skew * sr_best + (kurt - 1) / 4 * sr_best ** 2)
    return float(st.norm.cdf((sr_best - sr0) * np.sqrt(n_trades - 1) / den))


def funnel(h: pd.DataFrame, strats: list[Strategy], label: str) -> dict:
    sp = splits(h)
    tv_end = sp["VALIDATION"][1]
    h_tr = h[h["ts"] < sp["TRAIN"][1]].reset_index(drop=True)
    h_tv = h[h["ts"] < tv_end].reset_index(drop=True)  # TEST bars physically absent
    e_tr, e_tv = Engine(h_tr), Engine(h_tv)
    rows, srs = [], []
    for s in strats:
        t = e_tr.run(s)
        m = stats(t)
        if m["n"] >= 30 and np.isfinite(m["sr"]):
            srs.append(m["sr"])
        ok1 = (m["n"] >= 200 and m["pf"] >= 1.20 and (m["dd"] == 0 or m["tot"] / abs(m["dd"]) >= 3)
               and m["pos_years"] >= 0.70)
        rows.append({"key": s.key(), **{f"tr_{k}": v for k, v in m.items()}, "pass_train": ok1})
    df = pd.DataFrame(rows)
    # deflated Sharpe of the best TRAIN strategy among those with >= 200 trades
    cand = df[df["tr_n"] >= 200]
    dsr = None
    if len(cand):
        best = cand.loc[cand["tr_sr"].idxmax()]
        bs = strats[int(best.name)]
        r = e_tr.run(bs)["R"].to_numpy()
        dsr = {"strategy": bs.key(), "sr_per_trade": float(best["tr_sr"]), "n_trades": int(best["tr_n"]),
               "n_trials": len(strats), "sr_var_across_trials": float(np.var(srs)),
               "dsr_prob": deflated_sharpe(best["tr_sr"], len(r), float(st.skew(r)), float(st.kurtosis(r, fisher=False)),
                                           float(np.var(srs)), len(strats))}
    stage1 = [i for i in df.index[df["pass_train"]]]
    stage2 = []
    for i in stage1:
        s = strats[i]
        nb = [stats(e_tr.run(x))["pf"] for x in neighbours(s)]
        d1 = stats(e_tr.run(s, delay=1))["pf"]
        c2 = stats(e_tr.run(s, cost_mult=2))["pf"]
        ok = (len(nb) > 0 and min(nb) >= 1.0 and float(np.median(nb)) >= 1.10 and d1 >= 1.0 and c2 >= 1.0)
        df.loc[i, ["nb_min_pf", "nb_med_pf", "delay1_pf", "cost2_pf", "pass_robust"]] = [
            min(nb) if nb else np.nan, float(np.median(nb)) if nb else np.nan, d1, c2, ok]
        if ok:
            stage2.append(i)
    stage3 = []
    for i in stage2:
        m = stats(_window(e_tv.run(strats[i]), *sp["VALIDATION"]))
        ok = m["n"] >= 30 and m["exp"] > 0 and m["pf"] >= 1.10
        df.loc[i, ["va_n", "va_exp", "va_pf", "pass_val"]] = [m["n"], m["exp"], m["pf"], ok]
        if ok:
            stage3.append(i)
    frozen = sorted(stage3, key=lambda i: -df.loc[i, "tr_exp"])[:MAX_FROZEN]
    return {"label": label, "n_strategies": len(strats), "n_train_pass": len(stage1), "n_robust_pass": len(stage2),
            "n_val_pass": len(stage3), "frozen_idx": frozen, "deflated_sharpe": dsr, "table": df}


def test_eval(h: pd.DataFrame, strats: list[Strategy], idx: list[int]) -> dict:
    sp = splits(h)
    e = Engine(h)
    per, allr = [], []
    for i in idx:
        t = _window(e.run(strats[i]), *sp["TEST"])
        m = stats(t)
        r = t["R"].to_numpy(float)
        p = st.ttest_1samp(r, 0, alternative="greater").pvalue if len(r) > 2 else np.nan
        per.append({"idx": i, "key": strats[i].key(), **{f"te_{k}": v for k, v in m.items()}, "p_one_sided": p})
        allr.append(r)
    per = pd.DataFrame(per)
    if len(per):
        order = per["p_one_sided"].fillna(1).sort_values().index
        m_ = len(per); run = 0.0
        for rank, j in enumerate(order):
            run = max(run, min(1.0, (m_ - rank) * per.loc[j, "p_one_sided"] if np.isfinite(per.loc[j, "p_one_sided"]) else 1.0))
            per.loc[j, "p_holm"] = run
    port = np.concatenate(allr) if allr else np.array([])
    pp = st.ttest_1samp(port, 0, alternative="greater").pvalue if len(port) > 2 else np.nan
    return {"per_strategy": per, "portfolio": {"trades": int(len(port)), "exp_R": float(port.mean()) if len(port) else np.nan,
                                                "total_R": float(port.sum()), "p_one_sided": float(pp) if np.isfinite(pp) else None}}


def _summary(res):
    return {k: v for k, v in res.items() if k not in ("table",)}


def main(cmd: str):
    OUT.mkdir(parents=True, exist_ok=True)
    strats = generate()
    h = load_h1()
    if cmd == "stageA":
        res = funnel(h, strats, "REAL_GC")
        res["table"].to_csv(OUT / "stageA_real_table.csv.gz", index=False)
        frozen = [{"idx": i, "key": strats[i].key()} for i in res["frozen_idx"]]
        (OUT / "FROZEN_LIST.json").write_text(json.dumps({"frozen": frozen, "summary": _summary(res)}, indent=2, default=str))
        print(json.dumps(_summary(res), indent=1, default=str))
    elif cmd == "nulls":
        out = []
        for seed in NULL_SEEDS:
            hn = shuffled_null(h, seed)
            res = funnel(hn, strats, f"NULL_{seed}")
            te = test_eval(hn, strats, res["frozen_idx"])
            out.append({**_summary(res), "null_test_portfolio": te["portfolio"],
                        "null_test_n_holm_sig": int((te["per_strategy"].get("p_holm", pd.Series(dtype=float)) < 0.05).sum())})
            print(json.dumps(out[-1], indent=1, default=str), flush=True)
        (OUT / "NULLS.json").write_text(json.dumps(out, indent=2, default=str))
    elif cmd == "stageB":
        fz = json.loads((OUT / "FROZEN_LIST.json").read_text())
        idx = [f["idx"] for f in fz["frozen"]]
        assert all(strats[f["idx"]].key() == f["key"] for f in fz["frozen"]), "frozen list does not match generator"
        te = test_eval(h, strats, idx)
        te["per_strategy"].to_csv(OUT / "stageB_test_per_strategy.csv", index=False)
        (OUT / "TEST_RESULT.json").write_text(json.dumps({"portfolio": te["portfolio"]}, indent=2, default=str))
        print(te["per_strategy"].to_string()); print(te["portfolio"])


if __name__ == "__main__":
    main(sys.argv[1])
