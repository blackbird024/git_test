"""MAE / MFE, P&L a horizontes fijos y tiempo hasta fallar (diagnóstico; no cambia ninguna regla).

Zona de ruido (1 min): MAE/MFE en puntos desde el precio de entrada (con deslizamiento) usando máximos/mínimos de los
minutos en posición (el minuto de salida solo cuenta si la salida es al cierre). Horizontes: P&L sin costes si se
hubiera salido a +5/+15/+30/+60 min (apertura de ese minuto, sin pasar de 15:59), independientemente de la salida real.
RSI(2) (diario): MAE/MFE en % sobre la serie ajustada (máximos/mínimos de las sesiones en posición); horizontes de
1-5 sesiones (apertura de la sesión e+h).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"


def zona_ruido(ctx, ops: pd.DataFrame) -> pd.DataFrame:
    t = ctx.t.asi8
    ie = np.searchsorted(t, pd.DatetimeIndex(ops.t_entrada).asi8)
    ix = np.searchsorted(t, pd.DatetimeIndex(ops.t_salida).asi8)
    d = ops.direccion.to_numpy()
    ent = ops.entrada.to_numpy()
    cierre = (ops.motivo == "cierre").to_numpy()
    mae, mfe = np.zeros(len(ops)), np.zeros(len(ops))
    horiz = {h: np.full(len(ops), np.nan) for h in (5, 15, 30, 60)}
    en_benef_30 = np.full(len(ops), np.nan)
    for j in range(len(ops)):
        fin = ix[j] + 1 if cierre[j] else ix[j]
        fin = max(fin, ie[j] + 1)
        H, L = ctx.H[ie[j]:fin], ctx.L[ie[j]:fin]
        if d[j] == 1:
            mae[j], mfe[j] = max(0.0, ent[j] - L.min()), max(0.0, H.max() - ent[j])
        else:
            mae[j], mfe[j] = max(0.0, H.max() - ent[j]), max(0.0, ent[j] - L.min())
        dia = ctx.fecha[ie[j]]
        for h in horiz:
            k = ie[j] + h
            if k < len(t) and ctx.fecha[k] == dia and ctx.min_ny[k] < 960:
                horiz[h][j] = d[j] * (ctx.O[k] - ent[j])
        k = ie[j] + 30
        if ix[j] > k and ctx.fecha[min(k, len(t) - 1)] == dia:
            en_benef_30[j] = float(d[j] * (ctx.C[k - 1] - ent[j]) > 0)
    out = pd.DataFrame({"mae_pts": mae, "mfe_pts": mfe, "en_beneficio_a_30min": en_benef_30,
                        "duracion_min": (ops.t_salida - ops.t_entrada).dt.total_seconds().to_numpy() / 60})
    for h, v in horiz.items():
        out[f"pts_a_{h}min"] = v
    out["neto_pts"] = ops.neto.to_numpy() / 2.0
    return out


def rsi2(ops: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    """s: sesiones de nq_rsi2.preparar (open_aj, close_aj, high, low, close, t_primera)."""
    t0 = pd.DatetimeIndex(s.t_primera).asi8
    e = np.searchsorted(t0, pd.DatetimeIndex(ops.t_entrada).asi8)
    x = np.searchsorted(t0, pd.DatetimeIndex(ops.t_salida).asi8)
    h_aj = (s.high * s.close_aj / s.close).to_numpy()
    l_aj = (s.low * s.close_aj / s.close).to_numpy()
    oa = s.open_aj.to_numpy()
    mae, mfe = np.zeros(len(ops)), np.zeros(len(ops))
    horiz = {h: np.full(len(ops), np.nan) for h in range(1, 6)}
    for j in range(len(ops)):
        a, b = e[j], max(x[j], e[j] + 1)
        mae[j] = max(0.0, 1 - l_aj[a:b].min() / oa[a]) * 100
        mfe[j] = max(0.0, h_aj[a:b].max() / oa[a] - 1) * 100
        for h in horiz:
            if a + h < len(oa):
                horiz[h][j] = (oa[a + h] / oa[a] - 1) * 100
    out = pd.DataFrame({"mae_%": mae, "mfe_%": mfe, "sesiones": ops.sesiones.to_numpy()})
    for h, v in horiz.items():
        out[f"ret_%_a_{h}ses"] = v
    return out


def resumen_mae_mfe(ops: pd.DataFrame, tr: pd.DataFrame, col_mae: str, col_mfe: str) -> pd.DataFrame:
    gana = ops.neto.to_numpy() > 0
    filas = {}
    for nombre, m in (("ganadoras", gana), ("perdedoras", ~gana)):
        filas[nombre] = {"operaciones": int(m.sum()),
                         f"{col_mae} mediana": round(float(np.median(tr[col_mae][m])), 3),
                         f"{col_mae} p75": round(float(np.percentile(tr[col_mae][m], 75)), 3),
                         f"{col_mfe} mediana": round(float(np.median(tr[col_mfe][m])), 3),
                         f"{col_mfe} p75": round(float(np.percentile(tr[col_mfe][m], 75)), 3)}
    return pd.DataFrame(filas).T


def tiempo_hasta_fallar(ops: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    dur = tr.duracion_min
    cubos = pd.cut(dur, [-0.1, 1, 15, 30, 60, 1e9], labels=["≤ 1 min", "1-15 min", "15-30 min", "30-60 min", "> 60 min"])
    g = ops.assign(c=cubos.to_numpy()).groupby("c", observed=False)
    return pd.DataFrame({"operaciones": g.size(), "acierto_%": g.neto.apply(lambda s: round((s > 0).mean() * 100, 1)),
                         "expectativa_$": g.neto.mean().round(2), "neto_$": g.neto.sum().round(0)})
