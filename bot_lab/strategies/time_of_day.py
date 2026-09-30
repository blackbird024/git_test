"""BOT 21 — HORA DEL DÍA. Parte 1 (investigación): deriva media de NQ por franja horaria (no es una estrategia; ver
validation/regimenes.deriva_por_franja). Parte 2 (estrategias con hipótesis previa de la literatura):

Hipótesis: la "deriva nocturna" de los futuros de índices (Boyarchenko, Larsen y Whelan, 2023, "The Overnight
Drift", Review of Financial Studies): los rendimientos de los futuros de EE. UU. se concentran fuera del horario
regular, sobre todo en torno a la apertura europea (≈ 02:00-04:00 NY).

  21.1 Largo desde la reapertura de Globex (18:00 NY) hasta las 09:25 NY.
  21.2 Largo de 02:00 a 04:00 NY.
Sin stop (stop de catástrofe al 10 %) y sin objetivo; entrada y salida por tiempo con deslizamiento.
Se excluyen las sesiones en las que el contrato continuo cambia durante la posición (el salto de roll no es P&L).
"""
from __future__ import annotations

import numpy as np

from bot_lab.strategies import base as B

BOT = "21"
NOMBRE = "Hora del día (deriva nocturna)"
HIPOTESIS = ("Los rendimientos de los futuros de índices de EE. UU. se concentran fuera del horario regular, sobre todo "
             "en torno a la apertura europea (Boyarchenko, Larsen y Whelan, 2023).")
MARCO, SESION, FRECUENCIA = "1m", "noche", "intradia"

VARIANTES = {
    "21.1 largo 18:00→09:25 NY": dict(desde=18 * 60, hasta=565, cruza_medianoche=True),
    "21.2 largo 02:00→04:00 NY": dict(desde=120, hasta=240, cruza_medianoche=False),
}
BASE = "21.2 largo 02:00→04:00 NY"


def vecindad(p: dict) -> dict:
    d, h = p["desde"], p["hasta"]
    return {"entrada −30 min": {**p, "desde": d - 30}, "entrada +30 min": {**p, "desde": d + 30},
            "salida −30 min": {**p, "hasta": h - 30}, "salida +30 min": {**p, "hasta": h + 30}}


def ordenes(ctx, p: dict):
    ses = ctx.ses
    cambio_ses = np.r_[True, ses[1:] != ses[:-1]]
    ini_ses = np.flatnonzero(cambio_ses)
    fin_ses = np.r_[ini_ses[1:], len(ses)]
    filas = []
    for a, b in zip(ini_ses, fin_ses):
        m = ctx.min_ny[a:b]
        if p["cruza_medianoche"]:
            fecha_ny = ctx.fecha[a:b]
            # entrada: primer minuto de la sesión con hora >= desde (el día anterior); salida: hasta, día siguiente
            k_ent = np.flatnonzero((m >= p["desde"]) & (fecha_ny == fecha_ny[0]))
            k_sal = np.flatnonzero((m >= p["hasta"]) & (m < p["desde"]) & (fecha_ny != fecha_ny[0]))
        else:
            k_ent = np.flatnonzero((m >= p["desde"]) & (m < p["hasta"]))
            k_sal = np.flatnonzero((m >= p["hasta"]) & (m < p["hasta"] + 120))
        if len(k_ent) == 0 or len(k_sal) == 0:
            continue
        i_ent, i_sal = a + k_ent[0], a + k_sal[0]
        if i_sal <= i_ent or ctx.desfase[i_sal] != ctx.desfase[i_ent]:
            continue
        i_sig = i_ent - 1                                    # la orden a mercado se ejecuta en la apertura de i_ent
        filas.append((i_sig, i_sal, ctx.O[i_ent]))
    if not filas:
        return B.df_ordenes(i_sig=np.array([], int), dir=1, i_fin=np.array([], int))
    f = np.array(filas)
    return B.df_ordenes(i_sig=f[:, 0].astype(int), dir=1, stop_dist=0.1 * f[:, 2], i_fin=f[:, 1].astype(int))


def ejecutar(ctx, p: dict, mult: float = 1.0):
    o = B.cache(ctx, ("tod", tuple(sorted(p.items()))), lambda: ordenes(ctx, p))
    return B.correr(ctx, o, mult)
