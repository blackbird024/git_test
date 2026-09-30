"""Utilidades comunes de las estrategias del laboratorio.

Interfaz de cada módulo de estrategia:
    BOT, NOMBRE, HIPOTESIS, MARCO, SESION, FRECUENCIA ('intradia' | 'diaria')
    VARIANTES: dict nombre -> parámetros (pre-registrados). Clave especial "control": True = no seleccionable.
    BASE: nombre de la variante base.
    vecindad(params) -> dict nombre -> parámetros (sensibilidad pre-registrada alrededor de la variante elegida)
    ejecutar(ctx, params, mult=1.0) -> operaciones (DataFrame con t_entrada, t_salida, direccion, neto, bruto, r...)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.core.motor import simular

TICK = 0.25
FIN_RTH = 955          # 15:55 NY: salida por tiempo de las intradía


def cache(ctx, clave, fn):
    if not hasattr(ctx, "_lab_cache"):
        ctx._lab_cache = {}
    if clave not in ctx._lab_cache:
        ctx._lab_cache[clave] = fn()
    return ctx._lab_cache[clave]


def velas_ind(ctx, minutos: int) -> dict:
    """Velas de `minutos` de toda la sesión Globex con indicadores básicos (precios ajustados)."""
    def f():
        v = ctx.velas(minutos)
        d = {"v": v, "atr14": ind.atr(v.Ha, v.La, v.Ca, 14), "atr20": ind.atr(v.Ha, v.La, v.Ca, 20)}
        vw, sd = ctx.vwap_rth
        d["vwap"], d["sd"] = vw[v.i1], sd[v.i1]
        vg, sg = ctx.vwap_globex
        d["vwap_g"], d["sd_g"] = vg[v.i1], sg[v.i1]
        d["excluida"] = ctx.excluida[v.i1]
        return d
    return cache(ctx, ("velas", minutos), f)


def ema_de(ctx, minutos: int, n: int) -> np.ndarray:
    d = velas_ind(ctx, minutos)
    return cache(ctx, ("ema", minutos, n), lambda: ind.ema(d["v"].Ca, n))


def ventana(v, desde: int, hasta: int) -> np.ndarray:
    """Velas cuyo INICIO está en [desde, hasta) minutos NY."""
    return (v.min_ny >= desde) & (v.min_ny < hasta)


def misma_sesion_rth(v, b: np.ndarray, atras: int) -> np.ndarray:
    """True si la vela b - atras es del mismo día NY y está en RTH."""
    j = b - atras
    ok = j >= 0
    j = np.clip(j, 0, None)
    return ok & (v.fecha[j] == v.fecha[b]) & (v.min_ny[j] >= 570)


def fin_por_tiempo(ctx, v, b: np.ndarray, minuto_ny: int = FIN_RTH) -> np.ndarray:
    return ctx.fin_dia(v.fecha[b], minuto_ny)


def fin_tras_minutos(ctx, i_sig: np.ndarray, minutos: int, tope: np.ndarray) -> np.ndarray:
    """Primer minuto con t >= t[i_sig] + 1 + minutos (salida por tiempo), sin pasar de `tope`."""
    t = ctx.t.asi8
    objetivo = t[i_sig] + (minutos + 1) * 60_000_000_000
    k = np.searchsorted(t, objetivo, side="left")
    return np.minimum(k, tope)


def correr(ctx, ordenes: pd.DataFrame, mult: float, max_ses: int = 0, vwap: str = "rth") -> pd.DataFrame:
    if len(ordenes):
        ordenes = ordenes[ordenes.i_fin > ordenes.i_sig + 1]
        ordenes = ordenes[~ctx.excluida[ordenes.i_sig.to_numpy()]]
    return simular(ctx, ordenes, mult=mult, max_ses=max_ses, vwap=vwap)


def df_ordenes(**cols) -> pd.DataFrame:
    largos = [len(v) for v in cols.values() if not np.isscalar(v)]
    n = largos[0] if largos else 1
    return pd.DataFrame({k: (np.full(n, v) if np.isscalar(v) else np.asarray(v)) for k, v in cols.items()})
