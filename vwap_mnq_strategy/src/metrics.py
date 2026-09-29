"""Métricas de resultados.

Sharpe y Sortino: sobre rendimientos DIARIOS (P&L neto del día / capital al inicio del día), incluyendo los días sin
operaciones, anualizados con raíz de 252. Limitaciones: suponen rendimientos independientes e idénticamente
distribuidos; con colas gruesas y pocos datos sobrestiman la precisión. t de R: media / (desv / raíz(n)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def racha(mask: np.ndarray) -> int:
    mejor = actual = 0
    for v in mask:
        actual = actual + 1 if v else 0
        mejor = max(mejor, actual)
    return mejor


def resumen(trades: pd.DataFrame, daily: pd.DataFrame, capital: float, minutos_sesion: int = 390) -> dict:
    n = len(trades)
    out = {"operaciones": n}
    if n == 0:
        return out
    net, gross, r = trades.net_pnl, trades.gross_pnl, trades.r_net
    gan, per = net[net > 0], net[net < 0]
    eq = capital + daily.pnl.cumsum().to_numpy() if len(daily) else np.array([capital])
    pico = np.maximum.accumulate(np.r_[capital, eq])[1:]
    dd = eq - pico
    dd_pct = dd / pico
    cap_ini_dia = np.r_[capital, eq[:-1]]
    ret = daily.pnl.to_numpy() / cap_ini_dia if len(daily) else np.array([0.0])
    std = ret.std(ddof=1) if len(ret) > 1 else np.nan
    abajo = np.sqrt(np.mean(np.minimum(ret, 0) ** 2)) if len(ret) else np.nan
    dur = (pd.to_datetime(trades.exit_time) - pd.to_datetime(trades.entry_time)).dt.total_seconds() / 60
    out.update({
        "neto_usd": round(net.sum(), 0), "bruto_usd": round(gross.sum(), 0), "costes_usd": round(trades.costs.sum(), 0),
        "rentabilidad_%": round(net.sum() / capital * 100, 2),
        "win_rate_%": round((net > 0).mean() * 100, 1),
        "ganancia_media_usd": round(gan.mean(), 1) if len(gan) else 0.0,
        "perdida_media_usd": round(per.mean(), 1) if len(per) else 0.0,
        "expectativa_usd": round(net.mean(), 2), "expectativa_R": round(r.mean(), 4),
        "expectativa_R_bruta": round(trades.r_gross.mean(), 4),
        "t_R": round(r.mean() / r.std(ddof=1) * np.sqrt(n), 2) if n > 1 and r.std(ddof=1) > 0 else np.nan,
        "profit_factor": round(gan.sum() / -per.sum(), 3) if len(per) and per.sum() < 0 else np.inf,
        "max_dd_usd": round(dd.min(), 0), "max_dd_%": round(dd_pct.min() * 100, 2),
        "recovery_factor": round(net.sum() / -dd.min(), 2) if dd.min() < 0 else np.inf,
        "sharpe": round(ret.mean() / std * np.sqrt(252), 2) if std and std > 0 else np.nan,
        "sortino": round(ret.mean() / abajo * np.sqrt(252), 2) if abajo and abajo > 0 else np.nan,
        "duracion_media_min": round(dur.mean(), 1), "duracion_mediana_min": round(dur.median(), 1),
        "mae_medio_pts": round(trades.mae_pts.mean(), 2), "mfe_medio_pts": round(trades.mfe_pts.mean(), 2),
        "racha_perdedora_max": racha((net < 0).to_numpy()), "racha_ganadora_max": racha((net > 0).to_numpy()),
        "exposicion_%": round(dur.sum() / (len(daily) * minutos_sesion) * 100, 1) if len(daily) else np.nan,
        "operaciones_por_sesion": round(n / max(len(daily), 1), 2),
        "largos": int((trades.direction == 1).sum()), "cortos": int((trades.direction == -1).sum()),
    })
    return out


def por_grupo(trades: pd.DataFrame, clave: pd.Series) -> pd.DataFrame:
    g = trades.groupby(clave)
    return pd.DataFrame({"operaciones": g.size(), "neto_usd": g.net_pnl.sum().round(0),
                         "expectativa_R": g.r_net.mean().round(3), "win_rate_%": (g.net_pnl.apply(lambda x: (x > 0).mean()) * 100).round(1),
                         "t_R": g.r_net.apply(lambda x: x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan).round(2)})


def desgloses(trades: pd.DataFrame, b_atr_rank: pd.Series | None = None) -> dict:
    t = trades.copy()
    et = pd.to_datetime(t.entry_time, utc=True).dt.tz_convert("America/New_York")
    out = {"año": por_grupo(t, et.dt.year), "mes": por_grupo(t, et.dt.month),
           "dia_semana": por_grupo(t, et.dt.dayofweek.map({0: "lun", 1: "mar", 2: "mié", 3: "jue", 4: "vie"})),
           "hora_NY": por_grupo(t, et.dt.hour), "direccion": por_grupo(t, t.direction.map({1: "largo", -1: "corto"})),
           "motivo_salida": por_grupo(t, t.exit_reason)}
    q = pd.qcut(t.atr_entry, 4, labels=["ATR bajo", "ATR medio-bajo", "ATR medio-alto", "ATR alto"])
    out["volatilidad"] = por_grupo(t, q)
    return out


def bootstrap(trades: pd.DataFrame, n: int, seed: int, capital: float) -> dict:
    """Remuestreo con reemplazo de operaciones (mismo número) y barajado del orden. Supone operaciones
    independientes: ignora rachas de régimen, así que infravalora la probabilidad de periodos malos largos."""
    rng = np.random.default_rng(seed)
    x = trades.net_pnl.to_numpy()
    if len(x) < 2:
        return {}
    netos, dds = np.empty(n), np.empty(n)
    for i in range(n):
        s = rng.choice(x, size=len(x), replace=True)
        eq = capital + np.cumsum(s)
        pico = np.maximum.accumulate(np.r_[capital, eq])[1:]
        netos[i], dds[i] = s.sum(), (eq - pico).min()
    f = lambda v: float(round(v, 1))  # noqa: E731
    return {"neto_p5": f(np.percentile(netos, 5)), "neto_p50": f(np.percentile(netos, 50)),
            "neto_p95": f(np.percentile(netos, 95)), "prob_neto_negativo_%": f((netos < 0).mean() * 100),
            "max_dd_p50": f(np.percentile(dds, 50)), "max_dd_p5": f(np.percentile(dds, 5))}
