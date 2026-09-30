"""Performance statistics in R units (net of costs unless stated)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def max_consecutive_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def summarize(t: pd.DataFrame, trim_top_frac: float = 0.05) -> dict:
    if t is None or len(t) == 0:
        return {"trades": 0}
    t = t.sort_values("entry_time")
    r = t["R"].to_numpy(float)
    n = len(r)
    wins, losses = r[r > 0], r[r < 0]
    eq = np.cumsum(r)
    dd = eq - np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    # daily R series over NY trading dates with at least one trade -> Sharpe on active days, and on all weekdays
    day = t["entry_time"].dt.tz_convert("America/New_York").dt.date
    daily = pd.Series(r, index=day).groupby(level=0).sum()
    all_days = pd.bdate_range(min(daily.index), max(daily.index)).date
    daily_full = daily.reindex(all_days, fill_value=0.0)
    sharpe = float(daily_full.mean() / daily_full.std(ddof=1) * np.sqrt(252)) if daily_full.std(ddof=1) > 0 else np.nan
    monthly = pd.Series(r, index=t["entry_time"].dt.tz_convert("America/New_York").dt.tz_localize(None).dt.to_period("M")).groupby(level=0).sum()
    yearly = pd.Series(r, index=t["entry_time"].dt.tz_convert("America/New_York").dt.year).groupby(level=0).sum()
    srt = np.sort(r)[::-1]
    k = max(1, int(np.ceil(trim_top_frac * n)))
    gp = wins.sum()
    top10 = srt[:max(1, int(np.ceil(0.10 * n)))]
    tstat, p_two = stats.ttest_1samp(r, 0.0) if n > 2 else (np.nan, np.nan)
    p_one = (p_two / 2 if tstat > 0 else 1 - p_two / 2) if np.isfinite(p_two) else np.nan
    return {
        "trades": n,
        "win_rate": float((r > 0).mean()),
        "expectancy_R": float(r.mean()),
        "median_R": float(np.median(r)),
        "total_R": float(r.sum()),
        "gross_expectancy_R": float(t["gross_R"].mean()) if "gross_R" in t else np.nan,
        "profit_factor": float(gp / -losses.sum()) if losses.sum() < 0 else np.inf,
        "avg_win_R": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss_R": float(losses.mean()) if len(losses) else np.nan,
        "max_drawdown_R": float(dd.min()) if n else 0.0,
        "sharpe_daily_ann": sharpe,
        "max_consecutive_losses": max_consecutive_losses(r),
        "pct_positive_months": float((monthly > 0).mean()),
        "n_months": int(len(monthly)),
        "pct_positive_years": float((yearly > 0).mean()),
        "top10pct_share_of_gross_profit": float(top10[top10 > 0].sum() / gp) if gp > 0 else np.nan,
        f"expectancy_R_without_top{int(trim_top_frac * 100)}pct": float(srt[k:].mean()) if n > k else np.nan,
        "t_stat": float(tstat) if np.isfinite(tstat) else np.nan,
        "p_value_one_sided": float(p_one) if np.isfinite(p_one) else np.nan,
    }


def holm(pvals: dict[str, float], alpha: float) -> dict[str, dict]:
    items = sorted(((k, v if np.isfinite(v) else 1.0) for k, v in pvals.items()), key=lambda kv: kv[1])
    m = len(items)
    out, running, stop = {}, 0.0, False
    for rank, (k, p) in enumerate(items):
        adj = min(1.0, (m - rank) * p)
        running = max(running, adj)
        rej = (not stop) and p <= alpha / (m - rank)
        stop = stop or not rej
        out[k] = {"p_raw": p, "p_holm": running, "reject_H0": rej}
    return out


def period_table(t: pd.DataFrame, freq: str) -> pd.DataFrame:
    if len(t) == 0:
        return pd.DataFrame()
    ny = t["entry_time"].dt.tz_convert("America/New_York")
    key = ny.dt.tz_localize(None).dt.to_period(freq).astype(str)
    g = t.groupby(key)["R"]
    return pd.DataFrame({"trades": g.size(), "total_R": g.sum(), "expectancy_R": g.mean(),
                         "win_rate": g.apply(lambda x: (x > 0).mean())}).rename_axis("period").reset_index()
