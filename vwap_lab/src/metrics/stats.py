"""Métricas. Drawdown: sobre la curva de capital de operaciones CERRADAS (mismo método para todas las estrategias).
R = neto / riesgo inicial (contratos × |entrada − stop| × valor del punto). Profit factor = ganancias netas / |pérdidas
netas| ("inf" sin pérdidas; NaN sin operaciones). Bootstrap por bloques de DÍAS (no por operación)."""
import numpy as np
import pandas as pd


def summary(t: pd.DataFrame, n_sessions: int, capital0: float, session_minutes: int = 0):
    if t is None or len(t) == 0:
        return dict(n=0, sesiones=n_sessions)
    net = t["net_usd"].to_numpy()
    eq = capital0 + np.cumsum(net)
    peak = np.maximum.accumulate(np.r_[capital0, eq])[1:]
    dd = peak - eq
    i = int(np.argmax(dd)) if len(dd) else 0
    w, lo = net[net > 0], net[net < 0]
    costs = t["commission_usd"].sum() + t["slippage_usd"].sum()
    gross_pos = t.loc[t.gross_usd > 0, "gross_usd"].sum()
    streak = cur = 0
    for x in net:
        cur = cur + 1 if x < 0 else 0
        streak = max(streak, cur)
    mins = (pd.to_datetime(t["exit_time"].str[:19]) - pd.to_datetime(t["entry_time"].str[:19])).dt.total_seconds() / 60
    return dict(
        n=len(t), sesiones=n_sessions, ganadoras=int((net > 0).sum()), perdedoras=int((net < 0).sum()),
        acierto=float((net > 0).mean()), bruto=float(t["gross_usd"].sum()), costes=float(costs), neto=float(net.sum()),
        esperanza_usd=float(net.mean()), esperanza_R=float(t["R"].mean()),
        pf=float(w.sum() / -lo.sum()) if len(lo) and lo.sum() < 0 else (float("inf") if len(w) else float("nan")),
        gan_media=float(w.mean()) if len(w) else float("nan"), perd_media=float(lo.mean()) if len(lo) else float("nan"),
        ratio_gp=float(w.mean() / -lo.mean()) if len(w) and len(lo) else float("nan"),
        dd_usd=float(dd.max()) if len(dd) else 0.0, dd_pct=float(dd[i] / peak[i]) if len(dd) else 0.0,
        racha_perdedora=streak, ops_por_sesion=len(t) / max(n_sessions, 1),
        exposicion=float(mins.sum() / max(n_sessions * session_minutes, 1)) if session_minutes else float("nan"),
        costes_pct_bruto_positivo=float(costs / gross_pos) if gross_pos > 0 else float("nan"),
        ambiguas=int(t["ambiguous"].sum()),
    )


def day_block_bootstrap(t: pd.DataFrame, all_days, n=3000, block=5, seed=1):
    """IC90 de la esperanza en R por operación remuestreando BLOQUES DE DÍAS consecutivos (incluidos días sin operar)."""
    if len(t) < 10:
        return float("nan"), float("nan")
    days = pd.Index(sorted(all_days))
    g = t.groupby("date")
    sumR = g["R"].sum().reindex(days.astype(str), fill_value=0.0).to_numpy()
    cnt = g.size().reindex(days.astype(str), fill_value=0).to_numpy()
    m = len(days)
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(m / block))
    st = rng.integers(0, max(m - block + 1, 1), size=(n, nb))
    idx = (st[:, :, None] + np.arange(block)).reshape(n, -1)[:, :m]
    tot, k = sumR[idx].sum(1), cnt[idx].sum(1)
    est = tot / np.maximum(k, 1)
    return float(np.percentile(est, 5)), float(np.percentile(est, 95))
