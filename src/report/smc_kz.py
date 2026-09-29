"""Backtest de desarrollo de SMC_KZ_NQ_v1.0 (reglas: edges/smc_kill_zones_nq.md). Solo periodo de desarrollo.

Uso: python -m src.report.smc_kz   →   reports/SMC_KZ_NQ_v1.0/ (nunca se sobrescribe).
"""
from pathlib import Path

import pandas as pd

from src.data.datos import excluidos
from src.horas import NUEVA_YORK
from src.metrics.metricas import por_anio, resumen
from src.report.paso1 import desarrollo
from src.strategies import smc_sweep as smc

VERSION = "SMC_KZ_NQ_v1.0"
SALIDA = Path(__file__).resolve().parent.parent.parent / "reports" / VERSION

VARIANTES = {
    "A_original_0930_1530": smc.NASDAQ,
    "B_london_kz_0200_0500": smc.NASDAQ.con(zona=NUEVA_YORK, ventana=("02:00", "05:00"), cierre="08:25"),
    "C_ny_kz_0700_1000": smc.NASDAQ.con(zona=NUEVA_YORK, ventana=("07:00", "10:00"), cierre="12:00"),
}


def veredicto(r: dict) -> str:
    ok = r.get("operaciones", 0) > 1 and r["profit_factor"] > 1 and r["R_medio"] > 0 and r["t"] >= 2
    return "PASA al paso 2" if ok else "RECHAZADA"


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe.")
    m1, ex = desarrollo("NQ"), excluidos("NQ")
    filas, anuales, texto, tablas = [], [], [], {}
    for nombre, cfg in VARIANTES.items():
        ops, motivos = smc.backtest(m1, cfg, ex)
        r = resumen(ops)
        bruto = resumen(ops.assign(neto=ops.bruto, r=ops.bruto / ops.riesgo_usd)) if len(ops) else {}
        filas.append({"variante": nombre, **r, "PF_antes_costes": bruto.get("profit_factor"),
                      "R_medio_antes_costes": bruto.get("R_medio"), "veredicto": veredicto(r)})
        if len(ops):
            anuales.append(por_anio(ops).assign(variante=nombre))
            tablas[nombre] = ops
        texto.append(f"- {nombre}: {motivos}")
    SALIDA.mkdir(parents=True)
    for nombre, ops in tablas.items():
        ops.to_csv(SALIDA / f"{nombre}_trades.csv", index=False)
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA / "summary.csv", index=False)
    if anuales:
        pd.concat(anuales).to_csv(SALIDA / "yearly.csv")
    (SALIDA / "README.md").write_text("\n".join([
        f"# {VERSION}: desarrollo (sesiones < 22-mar-2023, 1 MNQ, costes estándar)", "",
        tabla.to_markdown(index=False), "", "Días por motivo:", *texto, "",
        "Criterio: PF > 1 y R medio > 0 con t ≥ 2 después de costes, por variante. Fuera de muestra sin tocar."]),
        encoding="utf-8")
    print(tabla.to_string(index=False))
    print("\n".join(texto))


if __name__ == "__main__":
    main()
