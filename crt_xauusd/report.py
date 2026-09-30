"""CSV outputs, charts and the final markdown report."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .metrics import period_table  # noqa: E402

# reference categorical palette (validated light-mode slots 1-3) + text/surface tokens
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
NEG = "#e34948"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
GROUP_COLOR = {"LONDON": C1, "NY": C2, "LONDON+NY": C3}

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
    "axes.titlecolor": INK, "lines.linewidth": 2, "legend.frameon": False,
})

TRADE_COLS = [
    "split", "setup_id", "kz", "direction", "ref_start_ny", "exec_start_ny", "ref_high", "ref_low", "ref_range",
    "sweep_time", "sweep_open", "sweep_high", "sweep_low", "sweep_close", "sweep_price", "sweep_depth",
    "sweep_depth_pct_range", "minutes_exec_start_to_sweep", "sweep_in_kz", "conf_bar_time", "confirm_open",
    "confirm_high", "confirm_low", "confirm_close", "confirm_body", "confirm_range", "confirm_wick",
    "confirm_body_ratio", "sweep_body", "engulf_body_ratio", "engulf_close_margin", "confirm_volume",
    "volume_sma20_prev", "volume_ratio", "volume_pctrank_prev", "confirm_close_back_inside_ref_range",
    "signal_time", "signal_price", "entry_time", "entry_price", "stop_price", "stop_distance", "target_price",
    "exit_time", "exit_price", "exit_reason", "cost_price", "gross_R", "R", "MFE_R", "MAE_R", "minutes_held",
    "minutes_to_MFE", "minutes_to_MAE", "overlaps_other_kz_trade", "other_direction_also_signalled",
    "ref_range_vs_median", "trend_efficiency_ratio", "vol_regime", "trend_regime",
]


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    if df is None or len(df) == 0:
        return "_(no rows)_\n"
    df = df.reset_index() if df.index.name or not isinstance(df.index, pd.RangeIndex) else df

    def f(x):
        if isinstance(x, (float, np.floating)):
            return "" if not np.isfinite(x) else floatfmt.format(x)
        return str(x)
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join(f(v) for v in row) + " |\n" for row in df.itertuples(index=False))


# ------------------------------------------------------------------ not evaluated
def write_not_evaluated(out: Path, cfg: dict, reason: str) -> None:
    txt = f"""# CRT XAUUSD — FINAL REPORT

## VERDICT

**NOT EVALUATED — no dataset.** None of the three allowed verdicts (ROBUST EDGE / PROMISING BUT
INSUFFICIENT / NO ROBUST EDGE) can be issued without data. No numbers in this repository come from
market data; no data was fabricated.

Reason: `{reason}`

Pre-registration version: `{cfg['preregistration_version']}`.

What is needed: see `docs/DATA_REQUIREMENTS.md`. Once `data/XAUUSD_M15.csv` and
`data/XAUUSD_M15.meta.json` exist, run:

```
python -m crt_xauusd.run            # TRAIN + VALIDATION only
python -m crt_xauusd.run --unlock-test   # only after the rules are frozen
```

Rules that will be evaluated: `docs/PREREGISTRATION.md`. Audit of the repository: `docs/AUDIT.md`.
"""
    (out / "CRT_XAUUSD_FINAL.md").write_text(txt)


# ------------------------------------------------------------------ charts
def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def charts(out: Path, groups: dict, res: dict) -> list[str]:
    ch = out / "charts"
    ch.mkdir(exist_ok=True)
    made = []
    tv_end = res["bounds"]["VALIDATION"][0]

    fig, ax = plt.subplots(figsize=(9, 4))
    for g, t in groups.items():
        if len(t):
            t = t.sort_values("entry_time")
            ax.plot(t["entry_time"], t["R"].cumsum(), color=GROUP_COLOR[g], label=g)
    ax.axvline(tv_end, color=INK2, lw=1, ls="--")
    ax.text(tv_end, ax.get_ylim()[1], " VALIDATION →", color=INK2, va="top", fontsize=8)
    ax.set_title("Equity curve (cumulative net R), BASE rule")
    ax.set_ylabel("R")
    ax.legend()
    _save(fig, ch / "equity_curve.png"); made.append("equity_curve.png")

    fig, ax = plt.subplots(figsize=(9, 3))
    for g, t in groups.items():
        if len(t):
            t = t.sort_values("entry_time")
            eq = t["R"].cumsum()
            ax.plot(t["entry_time"], eq - eq.cummax().clip(lower=0), color=GROUP_COLOR[g], label=g)
    ax.set_title("Drawdown (R)")
    ax.legend()
    _save(fig, ch / "drawdown.png"); made.append("drawdown.png")

    t = groups.get("LONDON+NY", pd.DataFrame())
    if len(t):
        for freq, name in (("M", "monthly_returns.png"), ("Y", "yearly_returns.png")):
            p = period_table(t, freq)
            fig, ax = plt.subplots(figsize=(9 if freq == "M" else 6, 3.2))
            ax.bar(p["period"], p["total_R"], color=[C1 if v >= 0 else NEG for v in p["total_R"]], width=0.8)
            ax.axhline(0, color=INK2, lw=0.8)
            ax.set_title(f"{'Monthly' if freq == 'M' else 'Yearly'} net R, LONDON+NY")
            if freq == "M":
                step = max(1, len(p) // 12)
                ax.set_xticks(range(0, len(p), step))
                ax.set_xticklabels(p["period"].iloc[::step], rotation=45, ha="right")
            _save(fig, ch / name); made.append(name)

        fig, ax = plt.subplots(figsize=(6, 3.2))
        ax.hist(t["R"], bins=40, color=C1, edgecolor=SURF, linewidth=1)
        ax.axvline(t["R"].mean(), color=INK, lw=1, ls="--", label=f"mean {t['R'].mean():.3f} R")
        ax.set_title("Distribution of net R per trade, LONDON+NY")
        ax.legend()
        _save(fig, ch / "r_distribution.png"); made.append("r_distribution.png")

        fig, ax = plt.subplots(figsize=(6, 4))
        win = t["R"] > 0
        ax.scatter(t.loc[win, "MAE_R"], t.loc[win, "MFE_R"], s=12, color=C1, label="winner", alpha=0.7)
        ax.scatter(t.loc[~win, "MAE_R"], t.loc[~win, "MFE_R"], s=12, color=C2, label="loser", alpha=0.7)
        ax.set_xlabel("MAE (R)"); ax.set_ylabel("MFE (R)")
        ax.set_title("MAE vs MFE, LONDON+NY")
        ax.legend()
        _save(fig, ch / "mae_mfe.png"); made.append("mae_mfe.png")

        for col, name, lab in (("volume_ratio", "volume_ratio_vs_outcome.png", "volume / SMA20(prev)"),
                               ("sweep_depth_pct_range", "sweep_size_vs_outcome.png", "sweep depth / ref 4H range")):
            fig, ax = plt.subplots(figsize=(6, 3.6))
            ax.scatter(t[col], t["R"], s=12, color=C1, alpha=0.6)
            ax.axhline(0, color=INK2, lw=0.8)
            ax.set_xlabel(lab); ax.set_ylabel("net R")
            ax.set_title(f"{lab} vs outcome, LONDON+NY")
            _save(fig, ch / name); made.append(name)

    rows = [(g, sp, s.get("expectancy_R", np.nan), s.get("trades", 0)) for (g, sp), s in res["summary"].items()
            if sp != "TRAIN+VALIDATION"]
    if rows:
        d = pd.DataFrame(rows, columns=["group", "split", "exp", "n"])
        sps = list(dict.fromkeys(d["split"]))
        fig, ax = plt.subplots(figsize=(7, 3.4))
        w = 0.8 / 3
        for k, g in enumerate(["LONDON", "NY", "LONDON+NY"]):
            dd = d[d.group == g].set_index("split").reindex(sps)
            ax.bar(np.arange(len(sps)) + (k - 1) * w, dd["exp"].fillna(0), width=w - 0.02, color=GROUP_COLOR[g], label=g)
        ax.set_xticks(range(len(sps))); ax.set_xticklabels(sps)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_ylabel("expectancy (net R/trade)")
        ax.set_title("London vs NY by split")
        ax.legend()
        _save(fig, ch / "london_vs_ny_by_split.png"); made.append("london_vs_ny_by_split.png")
    return made


# ------------------------------------------------------------------ full report
def _summ_table(res, groups_order, splits):
    keys = ["trades", "win_rate", "expectancy_R", "profit_factor", "total_R", "max_drawdown_R", "sharpe_daily_ann",
            "max_consecutive_losses", "pct_positive_months", "p_value_one_sided"]
    rows = []
    for g in groups_order:
        for sp in splits:
            s = res["summary"].get((g, sp), {})
            rows.append({"group": g, "split": sp, **{k: s.get(k) for k in keys}})
    return pd.DataFrame(rows)


def write_all(out: Path, cfg: dict, res: dict, groups: dict, sig, events, exec_skips) -> None:
    unlocked = res["unlocked"]
    allt = groups["LONDON+NY"]
    cols = [c for c in TRADE_COLS if c in allt.columns]
    allt[cols].to_csv(out / "CRT_XAUUSD_TRADES.csv", index=False)
    mae_cols = ["setup_id", "kz", "direction", "split", "entry_time", "exit_time", "exit_reason", "R", "MFE_R",
                "MAE_R", "minutes_held", "minutes_to_MFE", "minutes_to_MAE"]
    allt[[c for c in mae_cols if c in allt]].to_csv(out / "CRT_XAUUSD_MAE_MFE.csv", index=False)
    for freq, name in (("M", "MONTHLY"), ("Y", "YEARLY")):
        parts = [period_table(t, freq).assign(group=g) for g, t in groups.items() if len(t)]
        (pd.concat(parts) if parts else pd.DataFrame()).to_csv(out / f"CRT_XAUUSD_{name}.csv", index=False)
    res["walk_forward"].to_csv(out / "CRT_XAUUSD_WALK_FORWARD.csv", index=False)
    res["robustness"].to_csv(out / "CRT_XAUUSD_ROBUSTNESS.csv", index=False)
    if len(events):
        ev = events.copy()
        if not unlocked:
            ev = ev[pd.to_datetime(ev["sweep_bar_time"], utc=True) < res["bounds"]["TEST"][0]] if ev["sweep_bar_time"].notna().any() else ev
        ev.to_csv(out / "CRT_XAUUSD_SIGNAL_LOG.csv", index=False)
    (out / "RUN_MANIFEST.json").write_text(json.dumps(res["manifest"], indent=2, default=str))
    (out / "DATA_AUDIT.json").write_text(json.dumps(res["audit"], indent=2, default=str))
    made = charts(out, groups, res)

    v = res["verdict"]
    splits = ["TRAIN", "VALIDATION"] + (["TEST"] if unlocked else []) + ["TRAIN+VALIDATION"]
    S = []
    S.append(f"# CRT XAUUSD — FINAL REPORT\n\n## VERDICT\n\n**{v['verdict']}**\n\n")
    S.append(md_table(pd.DataFrame(v["by_group"]).T.rename_axis("group")))
    S.append(f"\n{v['note']}\n")
    if not unlocked:
        S.append("\nTEST is **LOCKED** (not computed). By rule, ROBUST EDGE cannot be issued while TEST is locked.\n")
    if res["manifest"].get("test_contamination_warning"):
        S.append(f"\n**WARNING:** {res['manifest']['test_contamination_warning']}\n")
    a = res["audit"]
    b = {k: [str(x), str(y)] for k, (x, y) in res["bounds"].items()}
    S.append(f"""
## 1. Dataset

Source: `{a['metadata'].get('source')}` · broker/feed: `{a['metadata'].get('broker')}` · price side:
`{a['metadata'].get('price_side')}` · **volume type: `{a['metadata'].get('volume_type')}`** · raw timestamps:
`{a['metadata'].get('timestamp_tz')}` (bar open) → converted to UTC → America/New_York (IANA, DST-aware).

```
{json.dumps({k: v for k, v in a.items() if k != 'metadata'}, indent=2, default=str)}
```

Splits (UTC, by signal time): TRAIN {b['TRAIN']} · VALIDATION {b['VALIDATION']} · TEST {b['TEST']}.
Manifest (git commit, hashes): `RUN_MANIFEST.json`.

## 2. Exact CRT definition
4H candles are built from 15M bars on New-York wall clock anchored at 17:00 (17/21/01/05/09/13).
Reference 4H = the complete 4H bucket immediately before the execution 4H. See docs/PREREGISTRATION.md.

## 3. Sweep definition
LONG: first 15M bar of the execution 4H with Low < Low_ref (strict). SHORT: first bar with High > High_ref.
Only the first penetration counts.

## 4. Confirmation definition (FVG/IFVG removed in pre-registration v2)
The IMMEDIATELY next 15M bar must body-engulf the sweep bar in the opposite direction:
LONG `C_s<O_s, C_c>O_c, O_c<=C_s, C_c>=O_s`; SHORT `C_s>O_s, C_c<O_c, O_c>=C_s, C_c<=O_s`.
Otherwise the setup direction is invalidated (no waiting window).

## 5. Volume definition
`volume_c >= {cfg['volume']['base']['threshold']} × mean(volume of previous 20 bars)`, current bar excluded.
Volume type in this dataset: **{a['metadata'].get('volume_type')}**.

## 6. Entry rules
OPEN of the 15M bar after the confirmation close. Confirmation bar must be inside the KZ and the execution 4H.

## 7. SL / TP
SL = min(Low_sweep, Low_confirm) − {cfg['execution']['stop_buffer_price']} (LONG; mirrored SHORT). TP = 1R.
Same-bar SL/TP → SL. Forced exit at last bar closing ≤ 17:00 NY.
Signals: {res['n_signals']} from {res['n_setups']} setups. Setup skips: {res['setup_skips']}. Execution skips: {res['exec_skips']}.
Rejection reasons (setups with a sweep that were invalidated): {res.get('rejection_reasons', {})}.

## 8–12. Results by kill zone and split (net of BASE costs)
""")
    S.append(md_table(_summ_table(res, ["LONDON", "NY", "LONDON+NY"], splits)))
    S.append("\nHolm correction over the 3 groups (TRAIN+VALIDATION, one-sided t-test mean R > 0):\n\n")
    S.append(md_table(pd.DataFrame(res["holm"]).T.rename_axis("group")))
    wf = res["walk_forward"]
    S.append("\n## 13. Walk-forward (frozen rule, no fitting)\n\n")
    if len(wf):
        agg = wf.groupby(["span", "group"]).agg(windows=("window", "nunique"),
                                                 oos_windows_with_trades=("oos_trades", lambda x: (x > 0).sum()),
                                                 pct_oos_positive=("oos_expectancy_R", lambda x: (x > 0).mean()),
                                                 median_oos_expectancy_R=("oos_expectancy_R", "median"))
        S.append(md_table(agg))
    S.append("\nFull table: `CRT_XAUUSD_WALK_FORWARD.csv`.\n")
    rob = res["robustness"]
    for title, kind in (("14. Cost sensitivity", "cost_multiplier"), ("15. Slippage sensitivity", "slippage_per_side"),
                        ("Entry delay", "entry_delay_bars"), ("Take-profit sensitivity (not hypotheses)", "take_profit"),
                        ("Volume-definition sensitivity (not hypotheses)", "volume_definition")):
        S.append(f"\n## {title} (TRAIN+VALIDATION)\n\n")
        S.append(md_table(rob[rob.kind == kind].drop(columns=["kind"])))
    S.append("\n## 16. Randomization / falsification (TRAIN+VALIDATION)\n\n")
    for g, fz in res["falsification"].items():
        S.append(f"\n**{g}**\n\n```\n{json.dumps(fz, indent=2, default=str)}\n```\n")
    S.append("\n## 17. MAE / MFE\n\n")
    if len(allt):
        tv = allt[allt["split"].isin(["TRAIN", "VALIDATION"])]
        S.append(md_table(tv.groupby("exit_reason")[["MFE_R", "MAE_R", "minutes_held", "minutes_to_MFE"]].median()))
        S.append("\nPer-trade data: `CRT_XAUUSD_MAE_MFE.csv`.\n")
    S.append("\n## 18. Regime analysis (descriptive; NOT filters)\n\n")
    for name, tb in res["regimes"].get("LONDON+NY", {}).items():
        S.append(f"\n**{name}**\n\n" + md_table(tb))
    S.append("\n## 19. Outlier dependence\n\n")
    rows = []
    for g in ["LONDON", "NY", "LONDON+NY"]:
        s = res["summary"][(g, "TRAIN+VALIDATION")]
        rows.append({"group": g, **{k: s.get(k) for k in s if "top" in k}})
    S.append(md_table(pd.DataFrame(rows)))
    S.append("\n## Success criteria checklist\n\n")
    S.append(md_table(pd.DataFrame(res["criteria"]).rename_axis("criterion")))
    S.append("""
`None` = not evaluable automatically (TEST locked, or economic coherence, which needs a written argument).

## 20. Weaknesses
- Volume is broker tick volume unless metadata says otherwise: it measures quote activity at ONE
  broker, not traded gold volume. The volume condition is therefore a proxy.
- Costs are ASSUMED placeholders unless replaced with the broker's actual spread/commission.
- 15M bars cannot resolve the intrabar order of SL and TP; the stop-first assumption biases results down.
- The 4H anchor (17:00 NY) is a convention; brokers with other server times draw different 4H candles.

## 21. Falsification conditions
The hypothesis is rejected if any of: TRAIN or VALIDATION expectancy ≤ 0 after costs; Holm p ≥ 0.05;
expectancy ≤ 0 at 2× costs; observed mean R not above the 95th percentile of the random-direction,
time-randomized, random-entry, volume-permutation or randomized-sweep nulls; TEST expectancy ≤ 0.

## 22. Next experiment
Decided only after reading this report, and recorded as a new pre-registration version BEFORE running it.
""")
    S.append("\n## Charts\n\n" + "".join(f"![{c}](charts/{c})\n" for c in made))
    (out / "CRT_XAUUSD_FINAL.md").write_text("".join(S))
