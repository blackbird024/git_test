"""Protocolo por BOT (CRITERIOS.md §5): cribado en TRAIN, selección con regla fija, puerta de cribado y VALIDATION."""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import metricas as M
from bot_lab.core.datos import tramo_de_fecha


def tramo_ops(ops: pd.DataFrame) -> np.ndarray:
    if len(ops) == 0:
        return np.array([], int)
    return tramo_de_fecha(pd.DatetimeIndex(ops.t_entrada))


def de_tramo(ops: pd.DataFrame, tramos) -> pd.DataFrame:
    if len(ops) == 0:
        return ops
    return ops[np.isin(tramo_ops(ops), list(tramos))].reset_index(drop=True)


def min_ops(mod, cfg: dict) -> int:
    return cfg["cribado"]["min_ops_diaria"] if mod.FRECUENCIA == "diaria" else cfg["cribado"]["min_ops_intradia"]


def seleccionar(tabla: pd.DataFrame, base: str, minimo: int, empate: float) -> tuple[str | None, str]:
    """Regla fija: mayor t entre las variantes no-control con muestra suficiente; si la base (o la más simple) está a
    menos de `empate` de t del mejor, gana la base."""
    ok = tabla[(~tabla.control) & (tabla.operaciones >= minimo) & tabla.t.notna()]
    if ok.empty:
        cand = tabla[~tabla.control & tabla.t.notna()]
        if cand.empty:
            return None, "ninguna variante con operaciones"
        mejor = cand.t.idxmax()
        return mejor, f"ninguna variante alcanza {minimo} operaciones; se toma la de mayor t (muestra insuficiente)"
    mejor = ok.t.idxmax()
    if base in ok.index and base != mejor and ok.t[mejor] - ok.t[base] < empate:
        return base, f"la base está a menos de {empate} de t de la mejor ({mejor}): se queda la base"
    return mejor, f"mayor t en TRAIN ({ok.t[mejor]:.2f}) entre {len(ok)} variantes con ≥ {minimo} operaciones"


def cribar(mod, ctx, cfg: dict, log=print) -> dict:
    """Ejecuta todas las variantes (una vez, sobre todo el contexto disponible) y evalúa SOLO el TRAIN."""
    filas, ops_var = {}, {}
    for nombre, p in mod.VARIANTES.items():
        o = mod.ejecutar(ctx, p)
        ops_var[nombre] = o
        tr = de_tramo(o, [0])
        filas[nombre] = {**M.rapidas(tr), "control": bool(p.get("control", False))}
    tabla = pd.DataFrame(filas).T
    tabla["control"] = tabla.control.astype(bool)
    for c in ("operaciones", "expectativa_$", "t", "profit_factor", "neto_$", "acierto_%"):
        tabla[c] = pd.to_numeric(tabla[c], errors="coerce")
    minimo = min_ops(mod, cfg)
    sel, motivo = seleccionar(tabla, mod.BASE, minimo, cfg["cribado"]["empate_t"])
    res = {"bot": mod.BOT, "nombre": mod.NOMBRE, "tabla_train": tabla, "seleccionada": sel, "motivo_seleccion": motivo,
           "n_variantes": len(mod.VARIANTES), "ops_variantes": ops_var}
    if sel is None:
        res.update(estado_cribado="E", detalle="sin operaciones")
        return res
    f = tabla.loc[sel]
    c = cfg["cribado"]
    muestra = f.operaciones >= minimo
    positiva = (f["expectativa_$"] > 0) and (f.profit_factor >= c["pf_min"]) and (f.t >= c["t_min"])
    if positiva and muestra:
        estado = "pasa"
    elif not muestra and f["expectativa_$"] > 0:
        estado = "C"
    else:
        estado = "E"
    res["estado_cribado"] = estado
    res["detalle"] = (f"TRAIN: {int(f.operaciones)} op., expectativa {f['expectativa_$']:.2f} $, PF {f.profit_factor:.2f}, "
                      f"t {f.t:.2f}")
    if estado == "pasa":
        val = de_tramo(ops_var[sel], [1])
        rv = M.rapidas(val)
        res["validacion"] = rv
        ok = rv["operaciones"] > 0 and rv["expectativa_$"] > 0 and rv["profit_factor"] >= cfg["validacion"]["pf_min"]
        res["estado_validacion"] = "finalista" if ok else "E"
    log(f"  BOT {mod.BOT} -> {sel}: {res['estado_cribado']} {res.get('estado_validacion', '')} ({res['detalle']})")
    return res
