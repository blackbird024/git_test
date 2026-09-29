"""Métricas. Sharpe/Sortino sobre rendimientos DIARIOS (P&L del día / capital al inicio del día, incluidos días sin
operaciones), x raíz(252); suponen independencia y subestiman el riesgo con colas gruesas. Calmar = rendimiento
anual compuesto / |drawdown máximo %|. t de R = media / (desv / raíz n)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def racha(m) -> int:
    best = cur = 0
    for v in m:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def summary(tr: pd.DataFrame, daily: pd.DataFrame, capital: float) -> dict:
    n = len(tr)
    if n == 0:
        return {"trades": 0}
    net, r = tr.net_pnl, tr.r_net
    win, loss = net[net > 0], net[net < 0]
    eq = capital + daily.pnl.cumsum().to_numpy()
    peak = np.maximum.accumulate(np.r_[capital, eq])[1:]
    dd, ddp = eq - peak, (eq - peak) / peak
    ret = daily.pnl.to_numpy() / np.r_[capital, eq[:-1]]
    sd = ret.std(ddof=1) if len(ret) > 1 else np.nan
    down = np.sqrt(np.mean(np.minimum(ret, 0) ** 2))
    dias = len(daily)
    anos = dias / 252
    cagr = (eq[-1] / capital) ** (1 / anos) - 1 if anos > 0 and eq[-1] > 0 else np.nan
    meses = pd.to_datetime(daily.session.astype(str)).dt.to_period("M")
    ret_mes = daily.groupby(meses.to_numpy()).pnl.sum()
    return {
        "trades": n, "win_rate_%": round((net > 0).mean() * 100, 1),
        "avg_win": round(win.mean(), 1) if len(win) else 0.0, "avg_loss": round(loss.mean(), 1) if len(loss) else 0.0,
        "avg_rr": round(win.mean() / -loss.mean(), 2) if len(win) and len(loss) else np.nan,
        "expectancy_usd": round(net.mean(), 2), "expectancy_R": round(r.mean(), 4), "expectancy_R_gross": round(tr.r_gross.mean(), 4),
        "t_R": round(r.mean() / r.std(ddof=1) * np.sqrt(n), 2) if n > 2 and r.std(ddof=1) > 0 else np.nan,
        "profit_factor": round(win.sum() / -loss.sum(), 3) if len(loss) else np.inf,
        "gross_profit": round(win.sum(), 0), "gross_loss": round(loss.sum(), 0),
        "gross_pnl": round(tr.gross_pnl.sum(), 0), "costs": round(tr.costs.sum(), 0), "net_pnl": round(net.sum(), 0),
        "max_dd": round(dd.min(), 0), "max_dd_%": round(ddp.min() * 100, 2),
        "sharpe": round(ret.mean() / sd * np.sqrt(252), 2) if sd and sd > 0 else np.nan,
        "sortino": round(ret.mean() / down * np.sqrt(252), 2) if down > 0 else np.nan,
        "calmar": round(cagr / -ddp.min(), 2) if ddp.min() < 0 and np.isfinite(cagr) else np.nan,
        "avg_trade": round(net.mean(), 2), "median_trade": round(net.median(), 2),
        "largest_win": round(net.max(), 0), "largest_loss": round(net.min(), 0),
        "max_consec_wins": racha((net > 0).to_numpy()), "max_consec_losses": racha((net < 0).to_numpy()),
        "avg_duration_min": round(tr.minutes.mean(), 1), "trades_per_day": round(n / max(dias, 1), 2),
        "return_per_month_usd": round(ret_mes.mean(), 0), "months_positive_%": round((ret_mes > 0).mean() * 100, 1),
        "longs": int((tr.direction == 1).sum()), "shorts": int((tr.direction == -1).sum()),
    }


def by(tr: pd.DataFrame, key) -> pd.DataFrame:
    g = tr.groupby(key)
    return pd.DataFrame({"trades": g.size(), "net_pnl": g.net_pnl.sum().round(0), "expectancy_R": g.r_net.mean().round(4),
                         "win_rate_%": g.net_pnl.apply(lambda s: round((s > 0).mean() * 100, 1)),
                         "t_R": g.r_net.apply(lambda s: round(s.mean() / s.std(ddof=1) * np.sqrt(len(s)), 2)
                                              if len(s) > 2 and s.std(ddof=1) > 0 else np.nan)})


def breakdowns(tr: pd.DataFrame, inst: dict) -> dict:
    t = tr.copy()
    et = pd.to_datetime(t.entry_time).dt.tz_localize("UTC").dt.tz_convert(inst["tz"])
    buckets = {k: (int(v[0][:2]) * 60 + int(v[0][3:]), int(v[1][:2]) * 60 + int(v[1][3:])) for k, v in inst["hour_buckets"].items()}
    franja = t.entry_min.map(lambda m: next((k for k, (a, b) in buckets.items() if a <= m < b), "otra"))
    vol = pd.qcut(t.atr_entry.rank(method="first"), 4, labels=["vol baja", "vol media-baja", "vol media-alta", "vol alta"])
    return {"año": by(t, et.dt.year), "mes": by(t, et.dt.month), "día semana": by(t, et.dt.dayofweek.map(dict(enumerate(["lun", "mar", "mié", "jue", "vie", "sáb", "dom"])))),
            "hora": by(t, et.dt.hour), "franja": by(t, franja), "dirección": by(t, t.direction.map({1: "long", -1: "short"})),
            "volatilidad (ATR entrada)": by(t, vol), "motivo de salida": by(t, t.exit_reason)}
