"""Métricas de auditoría. Entrada común: operaciones con columnas `neto` ($), `bruto` ($, opcional), `r` (opcional),
`t_entrada`, `t_salida` (UTC), y un P&L diario alineado por sesión (día de salida, hora de Nueva York).

t por operación: media / (desv / raíz n) — supone independencia.
IC por bloques: remuestreo de bloques de sesiones consecutivas del P&L diario (con su número de operaciones), que
conserva la dependencia de corto plazo; estadístico = P&L total / operaciones totales de la muestra remuestreada.
Sharpe/Sortino: P&L diario / capital, x raíz(252), incluyendo días sin operaciones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"


def a_ny(t) -> pd.DatetimeIndex:
    t = pd.DatetimeIndex(pd.to_datetime(t))
    return (t.tz_localize("UTC") if t.tz is None else t).tz_convert(NY)


def diario(ops: pd.DataFrame, sesiones: pd.DatetimeIndex) -> pd.DataFrame:
    """P&L y número de operaciones por sesión (día NY de salida), rellenando con 0 las sesiones sin operaciones."""
    dia = a_ny(ops.t_salida).normalize().tz_localize(None)
    g = pd.DataFrame({"pnl": ops.neto.to_numpy(), "n": 1}, index=dia).groupby(level=0).sum()
    idx = pd.DatetimeIndex(sesiones).normalize().union(g.index)
    return g.reindex(idx, fill_value=0.0)


def racha(mask) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def resumen(ops: pd.DataFrame, d: pd.DataFrame, capital: float) -> dict:
    n = len(ops)
    if n == 0:
        return {"operaciones": 0}
    x = ops.neto
    gan, per = x[x > 0], x[x < 0]
    eq = capital + d.pnl.cumsum().to_numpy()
    pico = np.maximum.accumulate(np.r_[capital, eq])[1:]
    dd = eq - pico
    ret = d.pnl.to_numpy() / np.r_[capital, eq[:-1]]
    sd = ret.std(ddof=1)
    abajo = np.sqrt(np.mean(np.minimum(ret, 0) ** 2))
    dur_h = (pd.to_datetime(ops.t_salida) - pd.to_datetime(ops.t_entrada)).dt.total_seconds() / 3600
    anos = max(len(d) / 252, 1e-9)
    out = {
        "operaciones": n, "operaciones_por_año": round(n / anos, 1),
        "neto_$": round(x.sum(), 0), "bruto_$": round(ops.bruto.sum(), 0) if "bruto" in ops else np.nan,
        "profit_factor": round(gan.sum() / -per.sum(), 3) if len(per) else np.inf,
        "expectativa_$": round(x.mean(), 2),
        "t_por_operacion": round(x.mean() / x.std(ddof=1) * np.sqrt(n), 2) if n > 2 else np.nan,
        "acierto_%": round((x > 0).mean() * 100, 1),
        "ganancia_media_$": round(gan.mean(), 1) if len(gan) else 0.0,
        "perdida_media_$": round(per.mean(), 1) if len(per) else 0.0,
        "max_dd_$": round(dd.min(), 0), "max_dd_%_capital": round((dd / pico).min() * 100, 2),
        "sharpe_diario_anual": round(ret.mean() / sd * np.sqrt(252), 2) if sd > 0 else np.nan,
        "sortino_diario_anual": round(ret.mean() / abajo * np.sqrt(252), 2) if abajo > 0 else np.nan,
        "horas_medias_en_mercado": round(dur_h.mean(), 2), "horas_medianas": round(dur_h.median(), 2),
        "racha_perdedora": racha((x < 0).to_numpy()), "racha_ganadora": racha((x > 0).to_numpy()),
    }
    if "r" in ops and ops.r.notna().any():
        r = ops.r.dropna()
        out["expectativa_R"] = round(r.mean(), 4)
        out["t_R"] = round(r.mean() / r.std(ddof=1) * np.sqrt(len(r)), 2) if len(r) > 2 else np.nan
    return out


def ic_bloques(d: pd.DataFrame, bloque: int, n: int, semilla: int, alfa: float = 0.05) -> tuple[float, float]:
    """IC del P&L medio por operación con bootstrap por bloques circulares sobre las sesiones."""
    pnl, cnt = d.pnl.to_numpy(float), d.n.to_numpy(float)
    m = len(pnl)
    if cnt.sum() < 2 or m < bloque:
        return (np.nan, np.nan)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(m / bloque))
    pnl2, cnt2 = np.r_[pnl, pnl[:bloque]], np.r_[cnt, cnt[:bloque]]      # circular
    cs_p, cs_c = np.r_[0, np.cumsum(pnl2)], np.r_[0, np.cumsum(cnt2)]
    stats = np.empty(n)
    for i in range(n):
        ini = rng.integers(0, m, k)
        sp = (cs_p[ini + bloque] - cs_p[ini]).sum()
        sc = (cs_c[ini + bloque] - cs_c[ini]).sum()
        stats[i] = sp / sc if sc > 0 else np.nan
    lo, hi = np.nanpercentile(stats, [100 * alfa / 2, 100 * (1 - alfa / 2)])
    return round(float(lo), 2), round(float(hi), 2)


def ic_iid(x: pd.Series, alfa: float = 0.05) -> tuple[float, float]:
    """IC normal de la media (supone independencia): media ± 1,96 · desv / raíz n."""
    x = pd.Series(x).dropna()
    if len(x) < 3:
        return (np.nan, np.nan)
    se = x.std(ddof=1) / np.sqrt(len(x))
    return round(x.mean() - 1.96 * se, 2), round(x.mean() + 1.96 * se, 2)


def por_periodo(ops: pd.DataFrame, freq: str) -> pd.DataFrame:
    t = a_ny(ops.t_salida)
    clave = t.to_period(freq).astype(str) if freq != "Y" else t.year
    g = ops.assign(k=np.asarray(clave)).groupby("k")
    return pd.DataFrame({"operaciones": g.size(), "neto_$": g.neto.sum().round(0),
                         "expectativa_$": g.neto.mean().round(2),
                         "acierto_%": g.neto.apply(lambda s: round((s > 0).mean() * 100, 1)),
                         "PF": g.neto.apply(lambda s: round(s[s > 0].sum() / -s[s < 0].sum(), 2) if (s < 0).any() else np.inf)})


def por_clave(ops: pd.DataFrame, clave: pd.Series, nombre: str) -> pd.DataFrame:
    g = ops.assign(**{nombre: np.asarray(clave)}).groupby(nombre)
    return pd.DataFrame({"operaciones": g.size(), "neto_$": g.neto.sum().round(0), "expectativa_$": g.neto.mean().round(2),
                         "t": g.neto.apply(lambda s: round(s.mean() / s.std(ddof=1) * np.sqrt(len(s)), 2) if len(s) > 2 else np.nan)})
