"""Clasificación automática A-E (CRITERIOS.md §7)."""
from __future__ import annotations

import numpy as np


def criterios(ev: dict, cfg: dict, baja_frecuencia: bool) -> dict:
    c = cfg["clasificacion"]
    m = ev["metricas"]
    ic = ev.get("IC95_bloques_$", (np.nan, np.nan))
    wf = ev.get("walk_forward", {}).get("reseleccion", {})
    mc = ev.get("montecarlo", {})
    minimo = c["min_ops_baja_frecuencia"] if baja_frecuencia else c["min_ops"]
    anual = m.get("neto_anual_$", 0)
    dd = m.get("max_dd_$", 0)
    return {
        "1 PF > 1.15": m.get("profit_factor", 0) > c["pf_a"],
        "2 expectativa > 0": m.get("expectativa_$", 0) > 0,
        "3 IC95 bloques > 0": bool(np.isfinite(ic[0]) and ic[0] > 0),
        f"4 operaciones ≥ {minimo}": m.get("operaciones", 0) >= minimo,
        "5 walk-forward positivo": bool(wf.get("expectativa_$", -1) > 0 and (wf.get("ventanas_positivas_%") or 0) >= 50),
        "6 estabilidad ≥ 0.70": ev.get("estabilidad", {}).get("estabilidad", 0) >= c["estabilidad_a"],
        "7 costes ×2 positivo": ev.get("costes", {}).get("STRESS_1", {}).get("expectativa_$", -1) > 0,
        "8 años positivos ≥ 60 %": m.get("frac_años_positivos", 0) >= c["anios_positivos"],
        "9 P(año negativo) < 30 %": mc.get("prob_año_negativo_%", 100) < c["prob_anio_negativo"] * 100,
        "10 neto anual / |DD| ≥ 0.33": bool(dd < 0 and anual / -dd >= c["calmar_min"]),
        "11 TEST > 0": ev.get("test", {}).get("expectativa_$", -1) > 0,
    }


def clase(ev: dict, cfg: dict, baja_frecuencia: bool) -> tuple[str, dict]:
    cr = criterios(ev, cfg, baja_frecuencia)
    obligatorios = [k for k in cr if k.split()[0] in ("2", "3", "4", "5", "7", "11")]
    est = ev.get("estabilidad", {}).get("estabilidad", 0)
    if all(cr[k] for k in obligatorios) and sum(cr.values()) >= 9:
        return "A — ROBUST", cr
    if est < cfg["clasificacion"]["estabilidad_fragil"] or not cr["7 costes ×2 positivo"]:
        return "D — FRAGILE", cr
    if not cr[[k for k in cr if k.startswith("4 ")][0]]:
        return "C — INSUFFICIENT", cr
    if not cr["2 expectativa > 0"]:
        return "E — NEGATIVE", cr
    return "B — PROMISING", cr
