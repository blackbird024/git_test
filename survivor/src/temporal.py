"""Análisis temporal con reglas congeladas: años, meses, ventanas móviles, walk-forward congelado, subperiodos,
concentración del beneficio, dependencia de valores atípicos, rachas frente a Monte Carlo y celdas por régimen con IC
por bloques."""
from __future__ import annotations

import numpy as np
import pandas as pd

from auditoria.src import metricas as mt

NY = "America/New_York"


def _pf(x) -> float:
    x = np.asarray(x, float)
    p = -x[x < 0].sum()
    return round(x[x > 0].sum() / p, 2) if p > 0 else np.inf


def _dd(x) -> float:
    eq = np.cumsum(np.asarray(x, float))
    return round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()), 0) if len(eq) else 0.0


def fechas_salida(ops):
    return pd.DatetimeIndex(pd.to_datetime(ops.t_salida, utc=True)).tz_convert(NY).tz_localize(None)


def por_ventana(ops: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Una fila por ventana de calendario (por fecha de SALIDA): operaciones, PF, expectativa, P&L, DD máx., acierto."""
    t = fechas_salida(ops)
    clave = t.to_period(freq)
    filas = []
    for k, g in ops.groupby(np.asarray(clave)):
        x = g.neto.to_numpy()
        filas.append({"ventana": str(k), "inicio": k.start_time.date(), "fin": k.end_time.date(), "operaciones": len(x),
                      "PF": _pf(x), "expectativa_$": round(x.mean(), 2), "P&L_$": round(x.sum(), 0), "max_dd_$": _dd(x),
                      "acierto_%": round((x > 0).mean() * 100, 1)})
    return pd.DataFrame(filas).set_index("ventana")


def subperiodos(ops: pd.DataFrame, cortes=((2015, 2017), (2018, 2020), (2021, 2023), (2024, 2026))) -> pd.DataFrame:
    y = fechas_salida(ops).year
    filas = {}
    for a, b in cortes:
        x = ops.neto.to_numpy()[(y >= a) & (y <= b)]
        filas[f"{a}-{b}"] = {"operaciones": len(x), "PF": _pf(x), "expectativa_$": round(x.mean(), 2) if len(x) else np.nan,
                             "P&L_$": round(x.sum(), 0), "max_dd_$": _dd(x)}
    return pd.DataFrame(filas).T


def mensual(diario: pd.Series) -> dict:
    m = diario.resample("ME").sum()
    eq = m.cumsum()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq.to_numpy()])[1:]
    return {"meses": len(m), "mediana_mensual_$": round(m.median(), 0), "meses_positivos_%": round((m > 0).mean() * 100, 1),
            "peor_mes_$": round(m.min(), 0), "peor_mes": str(m.idxmin().date()), "mejor_mes_$": round(m.max(), 0),
            "mejor_mes": str(m.idxmax().date()), "dd_mensual_max_$": round(float(dd.min()), 0),
            "racha_meses_negativos": mt.racha((m < 0).to_numpy())}


def moviles(diario: pd.Series, n_ops_dia: pd.Series) -> dict:
    """Ventanas móviles de 3, 6 y 12 meses sobre el P&L y el nº de operaciones mensuales."""
    m = diario.resample("ME").sum()
    n = n_ops_dia.resample("ME").sum()
    out = {}
    for k in (3, 6, 12):
        pnl = m.rolling(k).sum().dropna()
        ops = n.rolling(k).sum().reindex(pnl.index)
        exp = pnl / ops.replace(0, np.nan)
        neg = (pnl < 0).to_numpy()
        out[f"{k} meses"] = {"ventanas": len(pnl), "ventanas_negativas_%": round(neg.mean() * 100, 1),
                             "peor_$": round(pnl.min(), 0), "peor_hasta": str(pnl.idxmin().date()),
                             "expectativa_min_$": round(exp.min(), 2), "expectativa_mediana_$": round(exp.median(), 2),
                             "mayor_racha_ventanas_negativas": mt.racha(neg)}
    return {"tabla": pd.DataFrame(out).T, "serie_12m": m.rolling(12).sum()}


def concentracion(ops: pd.DataFrame, diario: pd.Series) -> dict:
    x = np.sort(ops.neto.to_numpy())[::-1]
    total = x.sum()
    out = {}
    for p in (1, 5, 10):
        k = max(1, int(round(len(x) * p / 100)))
        out[f"top {p}% operaciones ({k})"] = round(x[:k].sum() / total * 100, 1)
    m = diario.resample("ME").sum().sort_values(ascending=False)
    a = diario.groupby(diario.index.year).sum().sort_values(ascending=False)
    for k in (1, 3, 5):
        out[f"mejores {k} meses"] = round(m.iloc[:k].sum() / total * 100, 1)
    for k in (1, 2):
        out[f"mejores {k} años"] = round(a.iloc[:k].sum() / total * 100, 1)
    out["TAIL DEPENDENCE (top 10% > 100%)"] = out[[k for k in out if k.startswith("top 10%")][0]] > 100
    return out


def sin_mejores(ops: pd.DataFrame) -> pd.DataFrame:
    x = np.sort(ops.neto.to_numpy())[::-1]
    filas = {}
    for k in (0, 1, 3, 5, 10):
        y = x[k:]
        se = y.std(ddof=1) / np.sqrt(len(y))
        filas["original" if k == 0 else f"sin los {k} mejores"] = {"operaciones": len(y), "neto_$": round(y.sum(), 0),
                                                                    "expectativa_$": round(y.mean(), 2), "PF": _pf(y),
                                                                    "t": round(y.mean() / se, 2)}
    return pd.DataFrame(filas).T


def rachas_vs_mc(ops: pd.DataFrame, n: int, semilla: int) -> pd.DataFrame:
    x = ops.neto.to_numpy()
    rng = np.random.default_rng(semilla)
    obs_p, obs_g = mt.racha(x < 0), mt.racha(x > 0)
    sim_p, sim_g = np.empty(n), np.empty(n)
    for k in range(n):
        y = rng.permutation(x)
        sim_p[k], sim_g[k] = mt.racha(y < 0), mt.racha(y > 0)
    def fila(obs, sim):
        return {"observada": obs, "p5_MC": np.percentile(sim, 5), "p50_MC": np.percentile(sim, 50),
                "p95_MC": np.percentile(sim, 95), "percentil_de_la_observada": round((sim < obs).mean() * 100 + (sim == obs).mean() * 50, 1)}
    return pd.DataFrame({"racha perdedora máx.": fila(obs_p, sim_p), "racha ganadora máx.": fila(obs_g, sim_g)}).T


def distribucion_rachas(x: np.ndarray) -> dict:
    def longitudes(m):
        out, c = [], 0
        for v in m:
            if v:
                c += 1
            elif c:
                out.append(c)
                c = 0
        if c:
            out.append(c)
        return pd.Series(out).value_counts().sort_index().to_dict()
    return {"perdedoras": longitudes(x < 0), "ganadoras": longitudes(x > 0)}


def celdas(ops: pd.DataFrame, clave: np.ndarray, sesiones: pd.DatetimeIndex, minimo: int, n_boot: int, semilla: int,
           orden=None) -> pd.DataFrame:
    """Expectativa por celda con IC 95 % por bloques de 20 sesiones (P&L diario de la celda)."""
    filas = {}
    for k in pd.unique(clave):
        g = ops[clave == k]
        x = g.neto.to_numpy()
        ic = mt.ic_bloques(mt.diario(g, sesiones), 20, n_boot, semilla) if len(g) >= minimo else (np.nan, np.nan)
        filas[k] = {"operaciones": len(x), "PF": _pf(x), "expectativa_$": round(x.mean(), 2), "P&L_$": round(x.sum(), 0),
                    "IC95_$": ic, "acierto_%": round((x > 0).mean() * 100, 1),
                    "con_muestra": len(x) >= minimo}
    t = pd.DataFrame(filas).T
    if orden:
        t = t.reindex([o for o in orden if o in t.index] + [i for i in t.index if i not in orden])
    return t


def veredicto_regimen(t: pd.DataFrame) -> str:
    c = t[t.con_muestra.astype(bool) & (t.index != "sin dato")]
    if len(c) < 2:
        return "INCONCLUSIVE"
    exp = c["expectativa_$"].astype(float)
    sup = np.array([v[1] for v in c["IC95_$"]], float)
    total = c["P&L_$"].astype(float).sum()
    una = (c["P&L_$"].astype(float) > total).any() and (exp <= 0).sum() == len(c) - 1
    if (sup < 0).any() or una:
        return "CONTRADICTION"
    if (exp > 0).mean() >= 2 / 3:
        return "CONFIRMATION"
    return "WEAK EVIDENCE"
