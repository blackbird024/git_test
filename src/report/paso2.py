"""Paso 2: mejoras del RSI(2), de una en una, solo con el periodo de desarrollo.

Regla (fijada antes de ejecutar): un cambio se queda si mejora A LA VEZ el profit factor y el R medio
y tiene sentido causal. El filtro de volatilidad y el stop compiten por el mismo (tercer) parámetro libre:
se queda como mucho uno de los dos, el que más mejore el R medio.
"""
from pathlib import Path

import pandas as pd

from src.data.datos import excluidos
from src.metrics.metricas import resumen
from src.report.paso1 import desarrollo
from src.strategies import nq_rsi2

INFORMES = Path(__file__).resolve().parent.parent.parent / "reports"


def fila(nombre, cfg, nq, ex):
    ops = nq_rsi2.backtest(nq, cfg, ex)
    r = resumen(ops)
    return {"versión": nombre, **{k: r[k] for k in ("operaciones", "acierto_%", "profit_factor", "R_medio", "t",
                                                     "neto_$", "drawdown_max_$")},
            "peor_op_%": round(ops["ret_%"].min(), 2)}, r


def mejora(antes, despues) -> bool:
    return despues["profit_factor"] > antes["profit_factor"] and despues["R_medio"] > antes["R_medio"]


def ejecutar():
    nq, ex = desarrollo("NQ"), excluidos("NQ")
    texto = ["# Paso 2 — Mejoras del RSI(2) en NQ (solo periodo de desarrollo)", ""]
    base_cfg = nq_rsi2.Config()
    f0, r0 = fila("base (salida RSI > 70)", base_cfg, nq, ex)

    # 1) Salida rápida
    c1 = base_cfg.con(salida=60)
    f1, r1 = fila("salida RSI > 60", c1, nq, ex)
    queda1 = mejora(r0, r1)
    actual, r_act = (c1, r1) if queda1 else (base_cfg, r0)
    texto += ["## Cambio 1 — Salida rápida (RSI > 60 en vez de 70)", "",
              "Causa: el rebote que buscamos es corto; salir antes asegura la parte más fiable.", "",
              pd.DataFrame([f0, f1]).to_markdown(index=False), "",
              f"**Decisión: {'se queda' if queda1 else 'se descarta'}.**", ""]

    # 2) Filtro de volatilidad y 3) stop: compiten por el tercer parámetro
    c2 = actual.con(filtro_vol=1.5)
    c3 = actual.con(stop_atr=2.0)
    fa, _ = fila("actual", actual, nq, ex)
    f2, r2 = fila("+ filtro de volatilidad (ATR5/ATR50 <= 1,5)", c2, nq, ex)
    f3, r3 = fila("+ stop de catástrofe (2 x ATR14)", c3, nq, ex)
    candidatos = [(r2, c2, "filtro de volatilidad"), (r3, c3, "stop de catástrofe")]
    validos = [(r, c, n) for r, c, n in candidatos if mejora(r_act, r)]
    if validos:
        r_fin, final, nombre3 = max(validos, key=lambda x: x[0]["R_medio"])
    else:
        r_fin, final, nombre3 = r_act, actual, None
    texto += ["## Cambios 2 y 3 — Filtro de volatilidad frente a stop de catástrofe (compiten por el 3.er parámetro)", "",
              "Causa del filtro: en pánicos las caídas vienen de ventas forzadas que continúan.",
              "Causa del stop: limitar pérdidas extremas como la de febrero de 2020.", "",
              pd.DataFrame([fa, f2, f3]).to_markdown(index=False), "",
              f"**Decisión: {'se queda el ' + nombre3 if nombre3 else 'no se queda ninguno'}.**", "",
              "## Versión final para el paso 3", "", f"`{final}`", ""]
    (INFORMES / "paso2_mejoras.md").write_text("\n".join(texto), encoding="utf-8")
    return final, "\n".join(texto)
