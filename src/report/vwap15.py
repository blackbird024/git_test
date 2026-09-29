"""Backtest de desarrollo de VWAP_15M_2R_v1.0 (reglas: edges/vwap_15m_2r.md). Solo periodo de desarrollo.

Uso: python -m src.report.vwap15   →   reports/VWAP_15M_2R_v1.0/ (nunca se sobrescribe).
"""
from pathlib import Path

import pandas as pd

from src.data.datos import excluidos
from src.engine.costes import Costes
from src.engine.lookahead import comprobar
from src.metrics.metricas import por_anio, resumen
from src.report.paso1 import desarrollo
from src.strategies import vwap_15m as olv

SALIDA = Path(__file__).resolve().parent.parent.parent / "reports" / olv.VERSION
CORTES = [pd.Timestamp("2019-03-09", tz="UTC"), pd.Timestamp("2019-04-13", tz="UTC")]


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe.")
    m1, ex = desarrollo("NQ"), excluidos("NQ")
    tramo = m1[(m1.index >= "2019-02-01") & (m1.index < "2019-05-01")]
    fallos = comprobar(olv.senales, tramo, CORTES)
    variantes = {"OFICIAL": olv.Config(),
                 "sin_costes": olv.Config(costes=Costes(comision_lado=0.0, ticks_normal=0, ticks_apertura=0)),
                 }
    filas, texto, tablas = [], [], {}
    for nombre, cfg in variantes.items():
        ops, dias = olv.backtest(m1, cfg, ex)
        estados = {"dias": dias, "operaciones_por_dia": round(len(ops) / dias, 2)}
        r = resumen(ops)
        ok = r.get("operaciones", 0) > 1 and r["profit_factor"] > 1 and r["R_medio"] > 0 and r["t"] >= 2
        filas.append({"variante": nombre, **r, "cumple_criterio": ok})
        tablas[nombre] = ops
        texto.append(f"- {nombre}: {estados}")
    SALIDA.mkdir(parents=True)
    for nombre, ops in tablas.items():
        ops.to_csv(SALIDA / f"{nombre}_trades.csv", index=False)
    por_anio(tablas["OFICIAL"]).to_csv(SALIDA / "yearly.csv")
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA / "summary.csv", index=False)
    (SALIDA / "README.md").write_text("\n".join([
        f"# {olv.VERSION}: desarrollo (sesiones < 22-mar-2023, 1 MNQ)", "", tabla.to_markdown(index=False), "",
        "Por año (OFICIAL):", "", por_anio(tablas["OFICIAL"]).to_markdown(), "",
        "Días por estado:", *texto, "", f"Auditoría de look-ahead: {'OK' if not fallos else fallos}", "",
        "Criterio (solo la variante OFICIAL decide): PF > 1 y R medio > 0 con t ≥ 2 después de costes."]),
        encoding="utf-8")
    print(tabla.to_string(index=False))
    print("\n".join(texto))
    print("Look-ahead:", "OK" if not fallos else fallos)
    print(por_anio(tablas["OFICIAL"]).to_string())


if __name__ == "__main__":
    main()
