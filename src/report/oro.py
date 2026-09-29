"""CARTERA_ORO_v1.0: zona de ruido y RSI(2) en el oro con las reglas de NQ sin cambios (edges/cartera_oro.md).
NQ se calcula igual, como referencia de que el cálculo reproduce lo ya validado.

Uso: python -m src.report.oro   →   reports/CARTERA_ORO_v1.0/ (nunca se sobrescribe).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, inicio_fuera_de_muestra, velas_1m
from src.horas import sesion_cme
from src.metrics.metricas import resumen
from src.report.zona_ruido import metricas
from src.strategies import nq_rsi2, zona_ruido

SALIDA = Path(__file__).resolve().parent.parent.parent / "reports" / "CARTERA_ORO_v1.0"
MERCADOS = {"GC": {"valor_punto": 10.0, "tick": 0.10}, "NQ": {"valor_punto": 2.0, "tick": 0.25}}


def partir(ops: pd.DataFrame, col: str, corte) -> tuple[pd.DataFrame, pd.DataFrame]:
    ses = pd.Series(sesion_cme(pd.DatetimeIndex(ops[col]).tz_convert("UTC")), index=ops.index)
    return ops[ses < corte.date()], ops[ses >= corte.date()]


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe.")
    filas = []
    for raiz, esp in MERCADOS.items():
        m1, ex, corte = velas_1m(raiz), excluidos(raiz), inicio_fuera_de_muestra(raiz)
        anios = (m1.index[-1] - m1.index[0]).days / 365.25
        zr, _ = zona_ruido.backtest(m1, zona_ruido.Config(**esp), ex)
        rs = nq_rsi2.backtest(m1, nq_rsi2.Config(**esp), ex)
        for nombre, ops, col in (("zona_ruido", zr, "t_entrada"), ("rsi2", rs, "t_entrada")):
            for tramo, o in zip(("desarrollo", "posterior"), partir(ops, col, corte)):
                if o.empty:
                    filas.append({"mercado": raiz, "estrategia": nombre, "tramo": tramo, "operaciones": 0})
                    continue
                if nombre == "zona_ruido":
                    m = metricas(o.reset_index(drop=True), anios)
                    fila = {k: m[k] for k in ("operaciones", "acierto_%", "profit_factor", "media_$", "t", "neto_$",
                                              "drawdown_max_$")}
                else:
                    r = resumen(o)
                    fila = {"operaciones": r["operaciones"], "acierto_%": r["acierto_%"],
                            "profit_factor": r["profit_factor"], "media_$": round(o.neto.mean(), 2),
                            "R_medio": r["R_medio"], "t": r["t"], "neto_$": r["neto_$"],
                            "drawdown_max_$": r["drawdown_max_$"]}
                filas.append({"mercado": raiz, "estrategia": nombre, "tramo": tramo, **fila})
            if raiz == "GC":
                SALIDA.mkdir(parents=True, exist_ok=True)
                ops.to_csv(SALIDA / f"GC_{nombre}_trades.csv", index=False)
    tabla = pd.DataFrame(filas)
    SALIDA.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(SALIDA / "summary.csv", index=False)
    veredictos = []
    for est in ("zona_ruido", "rsi2"):
        d = tabla[(tabla.mercado == "GC") & (tabla.estrategia == est) & (tabla.tramo == "desarrollo")].iloc[0]
        p = tabla[(tabla.mercado == "GC") & (tabla.estrategia == est) & (tabla.tramo == "posterior")].iloc[0]
        media = d.get("R_medio", np.nan) if est == "rsi2" else d["media_$"]
        ok = d.operaciones > 1 and d.profit_factor > 1 and media > 0 and d.t >= 2 and p.profit_factor > 1
        veredictos.append(f"- {est} en oro: {'PASA' if ok else 'RECHAZADA'}")
    (SALIDA / "README.md").write_text("\n".join([
        "# CARTERA_ORO_v1.0 (reglas de NQ sin cambios; NQ como referencia)", "",
        "1 contrato micro fijo (MGC 10 $/punto, MNQ 2 $/punto); costes estándar del proyecto.", "",
        tabla.to_markdown(index=False), "", "Veredicto (criterio de edges/cartera_oro.md):", *veredictos]),
        encoding="utf-8")
    print(tabla.to_string(index=False))
    print("\n".join(veredictos))


if __name__ == "__main__":
    main()
