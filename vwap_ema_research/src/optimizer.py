"""Optimización SECUENCIAL por etapas (nunca todo a la vez). Regla fijada antes de ejecutar:

En cada etapa se prueban pocas opciones cambiando UN componente de la configuración actual.
  - Train optimiza: solo pasan las opciones que mejoran la expectativa neta en R de TRAIN frente a la actual y tienen
    al menos `min_trades_train` operaciones.
  - Validation selecciona: de esas, se elige la de mejor expectativa en VALIDATION, y solo si también mejora la de la
    configuración actual en validation. Si ninguna cumple, se mantiene la actual (menos parámetros).
  - El test no interviene.
Orden: modelo (A -> B -> C -> D, cada uno contra el actual), entrada, filtros de tendencia (uno a uno y luego juntos),
stop, take profit, salida, ventana horaria.
"""
from __future__ import annotations

import copy

import pandas as pd

from .common import Lab

CLAVES = ["trades", "win_rate_%", "expectancy_R", "expectancy_R_gross", "t_R", "profit_factor", "net_pnl", "max_dd_%",
          "sharpe", "months_positive_%"]


def evaluar(lab: Lab, p: dict) -> dict:
    return {per: lab.run(p, per)[1] for per in ("train", "validation")}


def etapa(lab: Lab, actual: dict, opciones: dict, nombre_etapa: str, min_trades: int, secuencial: bool = False):
    """opciones: {etiqueta: cambios}. Devuelve (nueva config, tabla de la etapa, etiqueta elegida)."""
    filas = []
    base = evaluar(lab, actual)
    filas.append({"etapa": nombre_etapa, "opcion": "(actual)", **{f"{k}_train": base["train"].get(k) for k in CLAVES},
                  **{f"{k}_val": base["validation"].get(k) for k in CLAVES}, "aceptada": None})
    elegida, cfg_actual, ref = "(actual)", actual, base
    candidatas = []
    for etiqueta, cambios in opciones.items():
        p = copy.deepcopy(cfg_actual if secuencial else actual)
        p.update(cambios)
        m = evaluar(lab, p)
        comparar = ref if secuencial else base
        pasa_train = m["train"].get("expectancy_R", -9) > comparar["train"].get("expectancy_R", -9) and m["train"].get("trades", 0) >= min_trades
        pasa_val = m["validation"].get("expectancy_R", -9) > comparar["validation"].get("expectancy_R", -9)
        filas.append({"etapa": nombre_etapa, "opcion": etiqueta, **{f"{k}_train": m["train"].get(k) for k in CLAVES},
                      **{f"{k}_val": m["validation"].get(k) for k in CLAVES}, "aceptada": bool(pasa_train and pasa_val)})
        if secuencial and pasa_train and pasa_val:                      # modelos: se acumula paso a paso
            cfg_actual, ref, elegida = p, m, etiqueta
        elif not secuencial and pasa_train and pasa_val:
            candidatas.append((m["validation"]["expectancy_R"], etiqueta, p))
    if not secuencial and candidatas:
        _, elegida, cfg_actual = max(candidatas, key=lambda c: c[0])
    return cfg_actual, pd.DataFrame(filas), elegida


def secuencia(lab: Lab, cfg: dict, p0: dict) -> tuple[dict, pd.DataFrame, list]:
    s, mt = cfg["search"], cfg["search"]["min_trades_train"]
    tablas, decisiones = [], []
    p, t, e = etapa(lab, p0, {f"modelo {m}": {"model": m} for m in s["models"][1:]}, "1 modelo", mt, secuencial=True)
    tablas.append(t); decisiones.append(("modelo", e))
    p, t, e = etapa(lab, p, {f"entrada {x}": {"entry_type": x} for x in s["entry_types"] if x != p["entry_type"]}, "2 entrada", mt)
    tablas.append(t); decisiones.append(("entrada", e))
    p, t, e = etapa(lab, p, {f"filtro {f}": {"trend_filters": [f]} for f in s["trend_filters"]}, "3 filtros (uno a uno)", mt)
    tablas.append(t); decisiones.append(("filtros", e))
    if e != "(actual)":
        p2, t, e2 = etapa(lab, p, {"filtros juntos": {"trend_filters": list(s["trend_filters"])}}, "3b filtros juntos", mt)
        tablas.append(t); decisiones.append(("filtros juntos", e2))
        p = p2
    stops = {f"stop {st} {m or ''}".strip(): {"stop_type": st, **({"atr_multiplier": m} if m else {})} for st, m in s["stops"]}
    p, t, e = etapa(lab, p, stops, "4 stop", mt)
    tablas.append(t); decisiones.append(("stop", e))
    p, t, e = etapa(lab, p, {f"TP {tp if tp else 'sin'}": {"take_profit_R": tp} for tp in s["take_profits"]}, "5 take profit", mt)
    tablas.append(t); decisiones.append(("take profit", e))
    salidas = {f"salida {x}{'' if v is None else ' ' + str(v) + ' min'}": {"exit_type": x, **({"time_exit_minutes": v} if v else {})}
               for x, v in s["exits"]}
    p, t, e = etapa(lab, p, salidas, "6 salida", mt)
    tablas.append(t); decisiones.append(("salida", e))
    p, t, e = etapa(lab, p, {f"solo {k}": {"window": v} for k, v in lab.inst["hour_buckets"].items()}, "7 ventana horaria", mt)
    tablas.append(t); decisiones.append(("ventana", e))
    return p, pd.concat(tablas, ignore_index=True), decisiones
