"""Walk-forward (CRITERIOS.md §6): ventanas de 12 meses de entrenamiento y 3 de prueba, avanzando 3 meses.

- Re-selección: en cada ventana se elige, con la misma regla fija del protocolo (mayor t, mínimo de operaciones,
  empate a favor de la base), una de las variantes PRE-REGISTRADAS del BOT usando solo su ventana de entrenamiento, y
  se aplica a los 3 meses siguientes.
- Parámetros fijos: la variante finalista en cada ventana de prueba (solo informa de la estabilidad temporal).
Las variantes se ejecutan una sola vez sobre todo el periodo; las ventanas solo cortan sus operaciones por fecha.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.validation.protocolo import seleccionar


def _t(x: np.ndarray) -> float:
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x))


def ejecutar(ops_variantes: dict, controles: set, base: str, fija: str, inicio: pd.Timestamp, fin: pd.Timestamp,
             meses_train: int, meses_test: int, min_ops: int, empate: float) -> dict:
    fechas = {k: pd.DatetimeIndex(o.t_entrada).tz_convert("America/New_York").tz_localize(None) if len(o) else
              pd.DatetimeIndex([]) for k, o in ops_variantes.items()}
    filas, oos, oos_fija = [], [], []
    q = pd.Timestamp(inicio) + pd.DateOffset(months=meses_train)
    while q + pd.DateOffset(months=meses_test) <= pd.Timestamp(fin) + pd.Timedelta(days=1):
        a, b = q - pd.DateOffset(months=meses_train), q + pd.DateOffset(months=meses_test)
        tabla = {}
        for k, o in ops_variantes.items():
            m = (fechas[k] >= a) & (fechas[k] < q)
            x = o.neto.to_numpy()[m] if len(o) else np.array([])
            tabla[k] = {"operaciones": len(x), "t": _t(x), "control": k in controles}
        tabla = pd.DataFrame(tabla).T
        tabla["t"] = pd.to_numeric(tabla.t)
        tabla["operaciones"] = pd.to_numeric(tabla.operaciones)
        tabla["control"] = tabla.control.astype(bool)
        sel, _ = seleccionar(tabla, base, min_ops, empate)
        fila = {"prueba_desde": q.date(), "prueba_hasta": (b - pd.Timedelta(days=1)).date(), "elegida": sel}
        for etiqueta, k, dest in (("reseleccion", sel, oos), ("fija", fija, oos_fija)):
            if k is None or len(ops_variantes[k]) == 0:
                fila[f"{etiqueta}_ops"], fila[f"{etiqueta}_neto_$"] = 0, 0.0
                continue
            m = (fechas[k] >= q) & (fechas[k] < b)
            o = ops_variantes[k][m]
            dest.append(o)
            fila[f"{etiqueta}_ops"], fila[f"{etiqueta}_neto_$"] = len(o), round(o.neto.sum(), 0)
        filas.append(fila)
        q = b
    ventanas = pd.DataFrame(filas)
    out = {"ventanas": ventanas}
    for etiqueta, lista in (("reseleccion", oos), ("fija", oos_fija)):
        o = pd.concat(lista, ignore_index=True) if lista else pd.DataFrame(columns=["neto"])
        col = ventanas[f"{etiqueta}_neto_$"] if len(ventanas) else pd.Series(dtype=float)
        con_ops = ventanas[f"{etiqueta}_ops"] > 0 if len(ventanas) else pd.Series(dtype=bool)
        out[etiqueta] = {
            "operaciones": len(o), "neto_$": round(o.neto.sum(), 0) if len(o) else 0.0,
            "expectativa_$": round(o.neto.mean(), 2) if len(o) else np.nan,
            "t": round(_t(o.neto.to_numpy()), 2) if len(o) > 2 else np.nan,
            "ventanas": int(len(ventanas)), "ventanas_con_ops": int(con_ops.sum()),
            "ventanas_positivas_%": round(float((col[con_ops] > 0).mean() * 100), 1) if con_ops.any() else np.nan,
        }
        out[f"ops_{etiqueta}"] = o
    return out
