"""Reglas de integridad del forward. Cada comprobación devuelve una lista de problemas (texto). Cualquier problema
GRAVE marca el día como INVALID con su explicación; nada se corrige en silencio."""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"
CAMPOS_COMPARAR = ["t_salida_utc", "precio_real_entrada", "precio_real_salida", "neto_$", "direccion"]


def operaciones(o: pd.DataFrame, m1: pd.DataFrame, inicio_utc: pd.Timestamp, estrategia: str) -> list[str]:
    if len(o) == 0:
        return []
    p = []
    te, ts = pd.DatetimeIndex(o.t_entrada_utc), pd.DatetimeIndex(o.t_salida_utc)
    if te.tz is None or str(te.tz) != "UTC":
        p.append("timestamps sin zona UTC")
    if (te < inicio_utc).any():
        p.append("operaciones con entrada anterior al inicio del forward")
    cerr = (o.estado == "CERRADA").to_numpy()
    if (ts[cerr] <= te[cerr]).any():
        p.append("operaciones con salida <= entrada")
    if o.id.duplicated().any():
        p.append(f"operaciones duplicadas: {list(o.id[o.id.duplicated()])}")
    orden = np.argsort(te.asi8, kind="stable")
    if len(o) > 1 and (te.asi8[orden][1:] < ts.asi8[orden][:-1])[cerr[orden][:-1]].any():
        p.append("dos operaciones abiertas a la vez en la misma estrategia")
    # precios posibles: el precio teórico debe estar dentro del rango de la vela de 1 min en que se ejecuta
    idx = m1.index.asi8
    for nombre, t, precio in (("entrada", te, o.precio_teorico_entrada), ("salida", ts, o.precio_teorico_salida)):
        k = np.searchsorted(idx, t.asi8)
        ok = (k < len(m1)) & (idx[np.clip(k, 0, len(m1) - 1)] == t.asi8)
        if nombre == "salida":
            ok &= cerr
        kk = np.clip(k, 0, len(m1) - 1)
        lo, hi = m1.low.to_numpy()[kk], m1.high.to_numpy()[kk]
        fuera = ok & ((precio.to_numpy() < lo - 1e-9) | (precio.to_numpy() > hi + 1e-9))
        if fuera.any():
            p.append(f"{int(fuera.sum())} precios de {nombre} fuera del rango de su vela (operación imposible)")
    # costes y deslizamiento aplicados como en el backtest
    d = np.where(o.direccion == "LARGO", 1, -1)
    desl_pts = d * (o.precio_real_entrada - o.precio_teorico_entrada) + d * (o.precio_teorico_salida - o.precio_real_salida)
    if not np.allclose(desl_pts[cerr] * 2.0, o["slippage_$"][cerr], atol=1e-6):
        p.append("el deslizamiento de los precios no coincide con slippage_$")
    if not np.allclose(o["bruto_sin_costes_$"] - o["slippage_$"] - o["comision_$"], o["neto_$"], atol=1e-6):
        p.append("neto != bruto − deslizamiento − comisión")
    if (o["comision_$"] <= 0).any() or (o["slippage_$"] <= 0).any():
        p.append("operaciones sin comisión o sin deslizamiento")
    # posiciones cerradas y exposición nocturna
    if estrategia == "NOISE_ZONE":
        mismo = te.tz_convert(NY).date == ts.tz_convert(NY).date
        if not mismo.all():
            p.append("zona de ruido con posición mantenida de noche (debe cerrarse en el día)")
        if (o.estado != "CERRADA").any():
            p.append("zona de ruido con posición sin cerrar")
    else:
        abiertas = int((o.estado == "ABIERTA").sum())
        if abiertas > 1:
            p.append("más de una posición RSI(2) abierta")
    return p


def append_only(registradas: pd.DataFrame, nuevas: pd.DataFrame) -> list[str]:
    """Las operaciones ya registradas deben reproducirse EXACTAMENTE al recalcular con más datos (si no, hay
    información del futuro, datos revisados o código cambiado)."""
    if registradas is None or len(registradas) == 0:
        return []
    p = []
    n = nuevas.set_index("id")
    for _, r in registradas.iterrows():
        if r.estado != "CERRADA":
            continue
        if r.id not in n.index:
            p.append(f"{r.id}: registrada antes y ya no aparece al recalcular")
            continue
        x = n.loc[r.id]
        for c in CAMPOS_COMPARAR:
            a, b = r[c], x[c]
            if c == "t_salida_utc":
                a, b = pd.Timestamp(a), pd.Timestamp(b)
            igual = (a == b) if not isinstance(a, float) else np.isclose(float(a), float(b), atol=1e-6)
            if not igual:
                p.append(f"{r.id}: {c} cambió al recalcular ({a} -> {b})")
    return p
