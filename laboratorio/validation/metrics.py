"""Métricas de una lista de operaciones. Todos los importes en USD por 1 contrato salvo que se indique otra cosa.

Sharpe y Sortino: sobre el P&L DIARIO (los días sin operación cuentan como 0) de una cuenta nominal, anualizados con
√252. Limitaciones: el P&L intradía no es normal, tiene colas gruesas y autocorrelación; con un contrato fijo el
"retorno" depende del capital nominal elegido, así que se calculan sobre USD y solo sirven para comparar estrategias
entre sí, no con fondos o índices.
"""
import numpy as np
import pandas as pd


def trades_frame(fills, cost, contracts=1) -> pd.DataFrame:
    t = pd.DataFrame([f.as_dict() for f in fills])
    if t.empty:
        return t
    t["date"] = pd.to_datetime(t["date"])
    pv = cost.point_value
    t["fixed_cost"] = 2 * cost.fixed_per_side * contracts
    t["slip_cost"] = 2 * cost.slip * pv * contracts      # aproximado: las salidas por objetivo no deslizan
    t.loc[t["reason"] == "objetivo", "slip_cost"] = cost.slip * pv * contracts
    t["pnl"] = t["gross_pts"] * pv * contracts - t["fixed_cost"]
    t["risk_usd"] = t["risk_pts"] * pv * contracts
    t["R"] = t["pnl"] / t["risk_usd"]
    t["minutes"] = t["exit_k"] - t["entry_k"]
    return t


def daily_pnl(t: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.Series:
    d = t.groupby("date")["pnl"].sum() if len(t) else pd.Series(dtype=float)
    return d.reindex(calendar, fill_value=0.0)


def max_dd(eq: pd.Series):
    peak = eq.cummax()
    dd = peak - eq
    if dd.max() <= 0:
        return 0.0, 0
    end = dd.idxmax()
    start = eq.loc[:end].idxmax()
    after = eq.loc[end:]
    rec = after[after >= eq.loc[start]]
    rec_days = (rec.index[0] - start).days if len(rec) else np.nan     # días naturales hasta recuperar
    return float(dd.max()), rec_days


def summary(t: pd.DataFrame, calendar: pd.DatetimeIndex, minutes_per_session=390) -> dict:
    if t is None or len(t) == 0:
        return dict(n=0)
    p = t["pnl"]
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    d = daily_pnl(t, calendar)
    eq = d.cumsum()
    dd, rec = max_dd(eq)
    yrs = max(len(calendar) / 252, 1e-9)
    sd = d.std(ddof=1)
    down = d[d < 0]
    sortino_den = np.sqrt((down ** 2).sum() / len(d)) if len(d) else np.nan
    top = p.sort_values(ascending=False)
    net = p.sum()
    by_year = t.groupby(t["date"].dt.year)["pnl"].sum()
    best_day = d.max()
    return dict(
        n=int(len(t)), ops_año=len(t) / yrs, neto=net, neto_año=net / yrs, pf=g / l if l > 0 else np.inf,
        esperanza=p.mean(), acierto=(p > 0).mean(), gan_media=p[p > 0].mean(), perd_media=p[p < 0].mean(),
        ratio_gp=(p[p > 0].mean() / -p[p < 0].mean()) if (p < 0).any() and (p > 0).any() else np.nan,
        R_medio=t["R"].mean() if "R" in t and t["R"].notna().any() else np.nan,
        dd_max=dd, dd_recuperacion_dias=rec,
        sharpe=d.mean() / sd * np.sqrt(252) if sd > 0 else np.nan,
        sortino=d.mean() / sortino_den * np.sqrt(252) if sortino_den > 0 else np.nan,
        exposicion=t["minutes"].sum() / (len(calendar) * minutes_per_session),
        coste_medio=(t["fixed_cost"] + t["slip_cost"]).mean(),
        dur_mediana_min=t["minutes"].median(),
        top10_ops_pct=top.head(10).sum() / net if net > 0 else np.nan,
        top5pct_ops_pct=top.head(max(1, len(top) // 20)).sum() / net if net > 0 else np.nan,
        mejor_dia=best_day, mejor_año_pct=by_year.max() / net if net > 0 else np.nan,
        años_pos=f"{(by_year > 0).sum()}/{len(by_year)}",
        racha_perdedora=_max_streak(p < 0),
    )


def _max_streak(mask):
    best = cur = 0
    for x in mask:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return best


def block_bootstrap_mean(x: np.ndarray, block=10, n_boot=5000, seed=7, q=(0.05, 0.95)):
    """IC del valor medio con bootstrap por bloques (respeta parte de la dependencia entre operaciones consecutivas)."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2 * block:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, nb))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    means = x[idx].mean(axis=1)
    return tuple(np.quantile(means, q))


def breakdown(t: pd.DataFrame, ctx: dict) -> dict:
    """Resultados por año, mes, día de la semana y régimen de volatilidad (terciles de ATR%, conocido antes)."""
    t = t.copy()
    t["vol"] = [ctx.get(d, {}).get("vol_rank", np.nan) if ctx else np.nan for d in t["date"]]
    t["regimen"] = pd.cut(t["vol"], [0, 1 / 3, 2 / 3, 1.0], labels=["baja", "media", "alta"])
    agg = lambda g: g["pnl"].agg(["count", "sum", "mean"])
    return dict(año=agg(t.groupby(t["date"].dt.year)), mes=agg(t.groupby(t["date"].dt.month)),
                dia_semana=agg(t.groupby(t["date"].dt.dayofweek)),
                regimen=agg(t.groupby("regimen", observed=True)))
