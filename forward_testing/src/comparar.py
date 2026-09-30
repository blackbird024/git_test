"""Comparación automática BACKTEST vs FORWARD por estrategia.

Referencia: operaciones del Survivor Analysis v1.0 (2015-01-02 -> 2026-09-28, NOT OUT-OF-SAMPLE).
Para cada métrica: valor backtest, valor forward, cociente forward/backtest y diferencia %. Además, la posición de la
media forward dentro de la distribución histórica de medias de N operaciones consecutivas (bootstrap de bloques):
"dentro de rango" si está entre p5 y p95. Con menos operaciones que el mínimo (ZR 50, RSI2 15) todo es DESCRIPTIVO y
no concluyente.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .deriva import bandas, pct_referencia


def _dd(x: np.ndarray) -> float:
    if len(x) == 0:
        return 0.0
    eq = np.cumsum(x)
    return float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())


def estadisticas(o: pd.DataFrame) -> dict:
    x = o["neto_$"].astype(float).to_numpy() if len(o) else np.array([])
    if len(x) == 0:
        return {"operaciones": 0}
    g, p = x[x > 0], x[x < 0]
    out = {"operaciones": len(x), "acierto_%": round((x > 0).mean() * 100, 1), "expectativa_$": round(x.mean(), 2),
           "mediana_$": round(float(np.median(x)), 2), "desviacion_$": round(float(x.std(ddof=1)), 2) if len(x) > 1 else np.nan,
           "profit_factor": round(g.sum() / -p.sum(), 2) if len(p) else np.inf, "neto_$": round(x.sum(), 0),
           "max_dd_$": round(_dd(x), 0), "p5_$": round(float(np.percentile(x, 5)), 1), "p25_$": round(float(np.percentile(x, 25)), 1),
           "p75_$": round(float(np.percentile(x, 75)), 1), "p95_$": round(float(np.percentile(x, 95)), 1)}
    if "neto_%" in o:
        y = o["neto_%"].astype(float).to_numpy()
        out["expectativa_%_precio"] = round(float(y.mean()), 4)
        out["mediana_%_precio"] = round(float(np.median(y)), 4)
        out["desviacion_%_precio"] = round(float(y.std(ddof=1)), 4) if len(y) > 1 else np.nan
    for c, n in (("duracion_min", "duracion_media_min"), ("mae_pts", "MAE_medio_pts"), ("mfe_pts", "MFE_medio_pts"),
                 ("slippage_$", "slippage_medio_$"), ("comision_$", "comision_media_$")):
        if c in o:
            out[n] = round(float(pd.to_numeric(o[c], errors="coerce").mean()), 2)
    return out


def referencia_estadisticas(ref: pd.DataFrame, estrategia: str | None = None) -> pd.DataFrame:
    """Normaliza las operaciones de referencia al mismo formato (neto_$, neto_%, duracion_min)."""
    r = pd.DataFrame({"neto_$": ref.neto.to_numpy()})
    if estrategia is not None and ("entrada" in ref or "ret_%" in ref):
        r["neto_%"] = pct_referencia(ref, estrategia)
    r["duracion_min"] = ((pd.to_datetime(ref.t_salida, utc=True) - pd.to_datetime(ref.t_entrada, utc=True)).dt.total_seconds() / 60).to_numpy()
    if "comision" in ref:
        r["comision_$"] = ref.comision.to_numpy()
    return r


def comparar(ref: pd.DataFrame, fwd: pd.DataFrame, minimo: int, mae_mfe_ref: pd.DataFrame | None = None,
             estrategia: str | None = None) -> dict:
    b = estadisticas(referencia_estadisticas(ref, estrategia) if "neto_$" not in ref else ref)
    if mae_mfe_ref is not None:
        b["MAE_medio_pts"] = round(float(mae_mfe_ref.mae_pts.mean()), 2)
        b["MFE_medio_pts"] = round(float(mae_mfe_ref.mfe_pts.mean()), 2)
    f = estadisticas(fwd)
    filas = []
    for k in b:
        if k == "operaciones":
            continue
        vb, vf = b.get(k), f.get(k, np.nan)
        cociente = vf / vb if isinstance(vb, (int, float)) and vb not in (0, np.inf) and pd.notna(vf) else np.nan
        filas.append({"métrica": k, "backtest": vb, "forward": vf, "forward/backtest": round(cociente, 2) if pd.notna(cociente) else np.nan,
                      "diferencia_%": round((cociente - 1) * 100, 1) if pd.notna(cociente) else np.nan})
    tabla = pd.DataFrame(filas).set_index("métrica")
    n = f.get("operaciones", 0)
    rango = {"operaciones_forward": n, "minimo_para_comparar": minimo, "concluyente": n >= minimo}
    if n >= 5:
        bd = bandas(ref.neto.to_numpy() if "neto" in ref else ref["neto_$"].to_numpy(), n)
        media = f["expectativa_$"]
        rango.update({"media_forward_$": media, "p5_hist_$": bd["p5"], "p95_hist_$": bd["p95"],
                      "dentro_de_rango_$": bool(bd["p5"] <= media <= bd["p95"])})
        if estrategia is not None and "neto_%" in fwd:
            bp = bandas(pct_referencia(ref, estrategia), n)
            mp = float(fwd["neto_%"].astype(float).mean())
            rango.update({"media_forward_%": round(mp, 4), "p5_hist_%": bp["p5"], "p95_hist_%": bp["p95"]})
        rango["dentro_de_rango"] = bool(bp["p5"] <= mp <= bp["p95"]) if "p5_hist_%" in rango else rango["dentro_de_rango_$"]
    return {"backtest": b, "forward": f, "tabla": tabla, "rango": rango}
