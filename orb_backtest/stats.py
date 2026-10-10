"""Métricas. Definiciones:
- R de una operación = resultado NETO / (contratos × |entrada efectiva − stop| × valor del punto). El riesgo inicial no
  incluye costes, así que un stop sin hueco da algo menos de −1R.
- Profit factor = suma de resultados netos positivos / |suma de negativos|. Sin pérdidas → "infinito"; sin operaciones →
  "no definido".
- Drawdown = máxima caída desde un máximo previo de la curva de capital al cierre de cada operación (en USD y en % de
  ese máximo). Al no marcar a mercado dentro de la operación, el drawdown intradía real puede ser mayor.
- Exposición = minutos con posición abierta / minutos de sesión regular de las sesiones válidas.
"""
import numpy as np
import pandas as pd


def _pf(x):
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    if len(x) == 0:
        return "no definido"
    return float(g / l) if l > 0 else "infinito"


def drawdown(equity: np.ndarray):
    if len(equity) == 0:
        return 0.0, 0.0
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    i = int(np.argmax(dd))
    return float(dd[i]), float(dd[i] / peak[i]) if peak[i] > 0 else float("nan")


def max_losing_streak(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def summary(t: pd.DataFrame, logs: pd.DataFrame, initial_equity: float, bar_minutes: int, session_minutes: int) -> dict:
    valid = logs[logs.status != "invalida"] if len(logs) else logs
    out = dict(sesiones=len(logs), sesiones_validas=len(valid), sesiones_invalidas=int((logs.status == "invalida").sum()) if len(logs) else 0,
               sesiones_sin_operacion=int((valid.status != "operada").sum()) if len(valid) else 0,
               descartadas_riesgo=int((logs.status == "descartada_riesgo").sum()) if len(logs) else 0,
               descartadas_hora=int((logs.status == "descartada_hora").sum()) if len(logs) else 0,
               descartadas_hueco=int((logs.status == "descartada_hueco").sum()) if len(logs) else 0,
               operaciones=len(t))
    if len(t) == 0:
        out.update(expectativa_R="no definido", profit_factor="no definido")
        return out
    net = t["net_usd"].to_numpy()
    eq = initial_equity + np.cumsum(net)
    dd, ddp = drawdown(np.concatenate([[initial_equity], eq]))
    wins, losses = net[net > 0], net[net < 0]
    out.update(
        acierto=float((net > 0).mean()), ganancia_media=float(wins.mean()) if len(wins) else float("nan"),
        perdida_media=float(losses.mean()) if len(losses) else float("nan"),
        resultado_bruto=float(t["gross_usd"].sum()), comisiones=float(t["commission_usd"].sum()),
        slippage=float(t["slippage_usd"].sum()), resultado_neto=float(net.sum()),
        expectativa_R=float(t["net_R"].mean()), R_mediana=float(t["net_R"].median()),
        profit_factor=_pf(net), dd_max_usd=dd, dd_max_pct=ddp, racha_perdedora_max=max_losing_streak(net),
        duracion_media_min=float(t["bars_held"].mean() * bar_minutes),
        exposicion=float(t["bars_held"].sum() * bar_minutes / max(len(valid) * session_minutes, 1)),
        contratos_medios=float(t["contracts"].mean()), riesgo_planificado_medio=float(t["planned_risk_usd"].mean()),
        operaciones_con_riesgo_real_sobre_presupuesto=int(t["warnings"].str.contains("presupuesto").sum()),
    )
    return out


def breakdown(t: pd.DataFrame) -> dict:
    if len(t) == 0:
        return {}
    d = pd.to_datetime(t["session"])
    g = lambda key: t.groupby(key).agg(operaciones=("net_usd", "size"), neto_usd=("net_usd", "sum"),
                                       R_medio=("net_R", "mean"), acierto=("net_usd", lambda x: (x > 0).mean()))
    out = {"año": g(d.dt.year), "mes": g(d.dt.month), "dia_semana": g(d.dt.day_name()), "direccion": g(t["side"]),
           "motivo_salida": g(t["exit_reason"])}
    if "vol_regime" in t:
        out["regimen_volatilidad"] = g(t["vol_regime"])
    return out


def bootstrap(R: np.ndarray, n=5000, seed=12345, block=1):
    """Remuestreo de la secuencia de R (con reemplazo; bloques de `block` operaciones). Supone que el futuro se parece
    al pasado y, con block=1, que las operaciones son independientes: subestima rachas si hay dependencia."""
    R = np.asarray(R, float)
    m = len(R)
    if m < 5:
        return {}
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(m / block))
    st = rng.integers(0, m - block + 1, size=(n, nb))
    idx = (st[:, :, None] + np.arange(block)).reshape(n, -1)[:, :m]
    S = R[idx]
    tot = S.sum(1)
    cum = np.cumsum(S, 1)
    dd = (np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), cum], 1), 1)[:, 1:] - cum).max(1)
    q = lambda x: {f"p{p}": float(np.percentile(x, p)) for p in (5, 25, 50, 75, 95)}
    return {"R_total": q(tot), "R_medio": q(tot / m), "dd_max_R": q(dd), "prob_R_total_negativo": float((tot < 0).mean()),
            "muestras": n, "bloque": block}


def split_dates(dates, fractions):
    dates = sorted(dates)
    n = len(dates)
    a = int(round(n * fractions[0]))
    b = int(round(n * (fractions[0] + fractions[1])))
    return {"desarrollo": (dates[0], dates[a - 1]), "validacion": (dates[a], dates[b - 1]), "test": (dates[b], dates[-1])}
