"""Métricas por partición, en R (1 contrato) y en USD con el tamaño por riesgo."""
import math

import numpy as np
import pandas as pd

from validation.metrics import block_bootstrap_mean


def _dd(eq: np.ndarray):
    """(máximo drawdown, duración máxima en número de observaciones) de una curva acumulada que empieza en 0."""
    if len(eq) == 0:
        return 0.0, 0
    e = np.concatenate([[0.0], eq])
    peak = np.maximum.accumulate(e)
    dd = e - peak
    longest = cur = 0
    for x in dd:
        cur = cur + 1 if x < 0 else 0
        longest = max(longest, cur)
    return float(dd.min()), int(longest)


def _streak(mask):
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def block_paths(x, n_trades, block=10, n=5000, seed=11):
    """Trayectorias bootstrap por bloques de `n_trades` operaciones (conserva rachas cortas)."""
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    nb = math.ceil(n_trades / block)
    starts = rng.integers(0, max(1, len(x) - block + 1), size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n, -1)[:, :n_trades]
    return x[np.clip(idx, 0, len(x) - 1)]


def ruin_probability(R, risk_usd, dd_limit, n_trades, block=10, n=5000, seed=11):
    """P(la pérdida acumulada desde el máximo llega a dd_limit dentro de n_trades) con riesgo fijo risk_usd por R.
    Hipótesis: el futuro se parece al pasado muestreado por bloques; drawdown medido sobre el saldo de cierre."""
    if len(R) < 2 * block:
        return np.nan
    p = block_paths(R, n_trades, block, n, seed) * risk_usd
    eq = np.cumsum(p, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), eq], axis=1), axis=1)[:, 1:]
    return float(((eq - peak) <= -dd_limit).any(axis=1).mean())


def maxdd_quantile(R, n_trades, q=0.95, block=10, n=5000, seed=11):
    if len(R) < 2 * block:
        return np.nan
    p = block_paths(R, n_trades, block, n, seed)
    eq = np.cumsum(p, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), eq], axis=1), axis=1)[:, 1:]
    return float(-np.quantile((eq - peak).min(axis=1), 1 - q))


def lag1_autocorr(x):
    x = np.asarray(x, float)
    if len(x) < 10:
        return np.nan
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def part_metrics(t: pd.DataFrame, days: pd.DataFrame, sized: pd.DataFrame = None) -> dict:
    """t: operaciones (1 contrato, columna R y net_usd_1c); days: registro de sesiones de la partición."""
    out = dict(sesiones=len(days),
               sesiones_con_senal=int(days.motivo.isin(["operacion", "sin_minuto_ejecutable",
                                                         "entrada_al_otro_lado_del_stop"]).sum()),
               operaciones=len(t))
    for k, v in days.motivo.value_counts().items():
        out["dias_" + k] = int(v)
    if len(t) == 0:
        return out
    t = t.sort_values("date")
    R = t.R.to_numpy()
    usd = t.net_usd_1c.to_numpy()
    win, loss = usd > 0, usd < 0
    gp, gl = usd[win].sum(), -usd[loss].sum()
    weeks = days.date.dt.to_period("W").nunique()
    months = days.date.dt.to_period("M").nunique()
    lo90, hi90 = block_bootstrap_mean(R, q=(0.05, 0.95))
    lo95, hi95 = block_bootstrap_mean(R, q=(0.025, 0.975))
    sd = R.std(ddof=1)
    tstat = R.mean() / (sd / math.sqrt(len(R))) if sd > 0 else np.nan
    ddR, ddlen = _dd(np.cumsum(R))
    # duración del drawdown en sesiones de calendario (días entre máximo y recuperación)
    eqd = pd.Series(R, index=t.date.values).groupby(level=0).sum()
    eqd = eqd.reindex(sorted(days.date.unique()), fill_value=0.0).cumsum()
    _, dd_days = _dd(eqd.to_numpy())
    dayR = eqd.diff().fillna(eqd.iloc[0])
    wk = pd.Series(R, index=pd.DatetimeIndex(t.date)).resample("W").sum()
    mo = pd.Series(R, index=pd.DatetimeIndex(t.date)).resample("ME").sum()
    srt = np.sort(usd)[::-1]
    out.update(
        ganadoras=int(win.sum()), perdedoras=int(loss.sum()), break_even=int((usd == 0).sum()),
        acierto=float(win.mean()), acierto_bruto_tp=float((t.reason == "tp").mean()),
        salidas={k: int(v) for k, v in t.reason.value_counts().items()},
        ganancia_bruta_usd_1c=float(gp), perdida_bruta_usd_1c=float(gl), neto_usd_1c=float(usd.sum()),
        profit_factor=float(gp / gl) if gl > 0 else np.nan,
        esperanza_usd_1c=float(usd.mean()), esperanza_R=float(R.mean()),
        esperanza_R_bruta=float(t.R_gross.mean()),
        ic90_R=[float(lo90), float(hi90)], ic95_R=[float(lo95), float(hi95)], t_stat=float(tstat),
        ganancia_media_usd_1c=float(usd[win].mean()) if win.any() else np.nan,
        perdida_media_usd_1c=float(usd[loss].mean()) if loss.any() else np.nan,
        ratio_ganancia_perdida=float(usd[win].mean() / -usd[loss].mean()) if win.any() and loss.any() else np.nan,
        R_total=float(R.sum()), R_por_semana=float(R.sum() / weeks), R_por_mes=float(R.sum() / months),
        ops_por_semana=float(len(t) / weeks), ops_por_mes=float(len(t) / months),
        minutos_medios_en_posicion=float(t.minutes_in_trade.mean()),
        riesgo_mediano_pts=float(t.r_pts.median()), riesgo_mediano_usd_1c=float(t.risk_usd_1c.median()),
        max_dd_R=ddR, duracion_max_dd_operaciones=ddlen, duracion_max_dd_sesiones=dd_days,
        racha_perdedora_max=_streak(loss), peor_dia_R=float(dayR.min()), peor_semana_R=float(wk.min()),
        peor_mes_R=float(mo.min()), mejor_mes_R=float(mo.max()), meses_positivos=float((mo > 0).mean()),
        perdidas_percentiles_R={f"p{p}": float(np.percentile(R[R < 0], p)) for p in (5, 25, 50, 75, 95)} if (R < 0).any() else {},
        stops_con_hueco=int((t.reason == "sl_hueco").sum()), ambiguas_sl_tp=int(t.ambiguous.sum()),
        top10_pct_del_neto=float(100 * srt[:10].sum() / usd.sum()) if usd.sum() > 0 else np.nan,
        autocorr_lag1_R=lag1_autocorr(R),
        largos=int((t.side == 1).sum()), cortos=int((t.side == -1).sum()),
    )
    if sized is not None and len(sized):
        z = sized.sort_values("date")
        eq = z.pnl_usd.cumsum().to_numpy()
        ddu, _ = _dd(eq)
        out.update(neto_usd_con_tamano=float(z.pnl_usd.sum()), max_dd_usd_con_tamano=ddu,
                   contratos_medios=float(z.contracts[z.contracts > 0].mean()) if (z.contracts > 0).any() else 0,
                   ops_sin_contrato=int((z.skipped == "no_cabe_un_contrato").sum()))
    return out


def by_group(t: pd.DataFrame, key) -> pd.DataFrame:
    g = t.groupby(key)
    return pd.DataFrame(dict(
        operaciones=g.size(), acierto=g.apply(lambda x: (x.net_usd_1c > 0).mean()),
        esperanza_R=g.R.mean(), R_total=g.R.sum(),
        profit_factor=g.apply(lambda x: x.net_usd_1c[x.net_usd_1c > 0].sum() / max(1e-9, -x.net_usd_1c[x.net_usd_1c < 0].sum())),
        neto_usd_1c=g.net_usd_1c.sum()))
