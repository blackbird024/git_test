"""BOT 26 — SPREAD ESTADÍSTICO. Parte oro/plata (GC/SI diarios de Databento). La parte NQ/ES queda pendiente de datos
(ver RESEARCH_LOG.md).

Hipótesis: los extremos del z-score del spread normalizado oro/plata revierten.

Reglas:
  1. Spread s = ln(GC ajustado) − ln(SI ajustado); z = (s − media 60 d) / desviación 60 d, al cierre diario.
  2. z < −Z -> largo spread (largo oro, corto plata); z > +Z -> corto spread. Entrada en la apertura siguiente.
  3. Salida en la apertura siguiente a que z cruce 0, o tras 20 sesiones.
Tamaño: 25.000 $ nocionales por pata (≈ 1 MGC y 1 SIL). Costes por operación completa: comisiones 1 $/lado/pata y
1 tick por lado y pata (MGC 1 $, SIL 5 $) = 16 $ × multiplicador.
Relación con el BOT 11 (pares oro/plata, 84 operaciones, insuficiente): misma familia; aquí con z-score fijo y
umbrales pre-registrados ±1 / ±1,5 / ±2. Días naturales UTC (liquidez a medianoche UTC: coste quizá infravalorado).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.strategies import base as B
from src.data.datos import sesiones_diarias_databento

BOT = "26"
NOMBRE = "Spread estadístico oro/plata"
HIPOTESIS = "Los extremos del z-score del spread normalizado oro/plata revierten."
MARCO, SESION, FRECUENCIA = "1D", "día UTC", "diaria"

VARIANTES = {
    "26.1 z ±1.0": dict(z=1.0, ventana=60, max_dias=20),
    "26.2 z ±1.5": dict(z=1.5, ventana=60, max_dias=20),
    "26.3 z ±2.0": dict(z=2.0, ventana=60, max_dias=20),
}
BASE = "26.2 z ±1.5"
NOCIONAL = 25000.0
COSTE_BASE = 16.0


def vecindad(p: dict) -> dict:
    out = {f"ventana={x}": {**p, "ventana": x} for x in (45, 75)}
    out.update({f"max_dias={x}": {**p, "max_dias": x} for x in (15, 25)})
    return out


def datos(hasta: pd.Timestamp) -> pd.DataFrame:
    g, s = sesiones_diarias_databento("GC"), sesiones_diarias_databento("SI")
    df = pd.DataFrame({"g_c": g.close_aj, "g_o": g.open_aj, "s_c": s.close_aj, "s_o": s.open_aj,
                       "t0": g.t_primera}).dropna()
    return df[df.index < hasta]


def ejecutar(ctx, p: dict, mult: float = 1.0) -> pd.DataFrame:
    hasta = pd.Timestamp(ctx.fecha[-1]) + pd.Timedelta(days=1)
    df = B.cache(ctx, ("gcsi", hasta), lambda: datos(hasta))
    sp = np.log(df.g_c) - np.log(df.s_c)
    z = ((sp - sp.rolling(p["ventana"]).mean()) / sp.rolling(p["ventana"]).std()).to_numpy()
    go, so = df.g_o.to_numpy(), df.s_o.to_numpy()
    t0 = list(df.t0)
    n, i, ops = len(df), 0, []
    while i < n - 1:
        if not np.isfinite(z[i]) or abs(z[i]) <= p["z"]:
            i += 1
            continue
        d = 1 if z[i] < 0 else -1                 # largo spread = largo oro / corto plata
        e = i + 1
        k = e
        while k < n - 1 and k - e + 1 < p["max_dias"]:
            if np.sign(z[k]) != np.sign(z[i]):
                break
            k += 1
        x = min(k + 1, n - 1)
        ret = d * ((go[x] / go[e] - 1) - (so[x] / so[e] - 1))
        bruto = NOCIONAL * ret
        coste = COSTE_BASE * mult
        ops.append({"t_entrada": t0[e], "t_salida": t0[x], "direccion": d, "sesiones": x - e, "bruto": bruto,
                    "comision": coste, "neto": bruto - coste, "r": np.nan,
                    "motivo": "z0" if np.sign(z[k]) != np.sign(z[i]) else "tiempo"})
        i = x
    o = pd.DataFrame(ops, columns=["t_entrada", "t_salida", "direccion", "sesiones", "bruto", "comision", "neto", "r",
                                   "motivo"])
    if len(o):
        o["t_entrada"] = pd.to_datetime(o.t_entrada, utc=True)
        o["t_salida"] = pd.to_datetime(o.t_salida, utc=True)
    return o
