"""Informe de la fase de desarrollo del London Range Breakout (solo datos anteriores al corte)."""
from pathlib import Path

import pandas as pd

from src.data.datos import excluidos, inicio_fuera_de_muestra
from src.engine.costes import Costes
from src.metrics.detalle import completas, desgloses
from src.report.paso1 import desarrollo
from src.strategies import london_range_breakout as lrb

INFORMES = Path(__file__).resolve().parent.parent.parent / "reports"


def ejecutar():
    gc, ex = desarrollo("GC"), excluidos("GC")
    netas, motivos = lrb.backtest(gc, lrb.Config(), ex)
    brutas, _ = lrb.backtest(gc, lrb.Config(costes=Costes(comision_lado=0, ticks_normal=0, ticks_apertura=0)), ex)
    m_neto, m_bruto = completas(netas), completas(brutas)
    d = desgloses(netas)
    t = ["# London Range Breakout en el oro — fase de DESARROLLO", "",
         f"Periodo: {gc.index.min().date()} → {gc.index.max().date()} (fuera de muestra desde "
         f"{inicio_fuera_de_muestra('GC').date()}: NO cargado). Tamaño: 1 MGC.", "",
         f"Días: {motivos}", "",
         "## Antes y después de costes", "",
         pd.DataFrame({"antes de costes": m_bruto, "después de costes": m_neto}).to_markdown(), "",
         f"Salidas: {netas.motivo.value_counts().to_dict()}", "",
         f"Distancia media al stop (1R): {netas.rango_usd.mean():.2f} $ de precio "
         f"(mediana {netas.rango_usd.median():.2f} $)", ""]
    for nombre, tabla in d.items():
        t += [f"## {nombre.replace('_', ' ').capitalize()} (después de costes)", "", tabla.to_markdown(), ""]
    (INFORMES / "london_breakout_desarrollo.md").write_text("\n".join(t), encoding="utf-8")
    return "\n".join(t), netas, brutas
