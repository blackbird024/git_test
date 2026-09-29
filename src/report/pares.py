"""Backtest de PARES_ORO_PLATA_v1.0 (reglas: edges/pares_oro_plata.md).

Uso: python -m src.report.pares   →   reports/PARES_ORO_PLATA_v1.0/ (nunca se sobrescribe).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import inicio_fuera_de_muestra, sesiones_diarias_databento
from src.metrics.metricas import racha
from src.strategies import pares_oro_plata as p

SALIDA = Path(__file__).resolve().parent.parent.parent / "reports" / p.VERSION


def metricas(o: pd.DataFrame, col: str = "neto") -> dict:
    if o.empty:
        return {"operaciones": 0}
    n = o[col]
    eq = n.cumsum().to_numpy()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]
    perdido = -n[n < 0].sum()
    return {"operaciones": len(o), "acierto_%": round((n > 0).mean() * 100, 1),
            "profit_factor": round(n[n > 0].sum() / perdido, 2) if perdido > 0 else float("inf"),
            "media_$": round(n.mean(), 1), "t": round(n.mean() / n.std() * np.sqrt(len(n)), 2) if len(n) > 1 else np.nan,
            "neto_$": round(n.sum(), 0), "peor_$": round(n.min(), 0), "drawdown_max_$": round(dd.min(), 0),
            "racha_perdedora": racha(n < 0), "sesiones_media": round(o.sesiones.mean(), 1)}


def main() -> None:
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe.")
    corte = inicio_fuera_de_muestra("diario_GC")
    assert corte == inicio_fuera_de_muestra("diario_SI")
    d = p.preparar(sesiones_diarias_databento("GC"), sesiones_diarias_databento("SI"), p.Config())
    ops = p.backtest(d, p.Config())
    dev, oos = ops[ops.t_entrada < corte], ops[ops.t_entrada >= corte]
    filas = [{"tramo": "desarrollo", **metricas(dev)}, {"tramo": "fuera_de_muestra", **metricas(oos)},
             {"tramo": "completo", **metricas(ops)}, {"tramo": "completo_sin_costes", **metricas(ops, "bruto")}]
    tabla = pd.DataFrame(filas)
    rd, ro = filas[0], filas[1]
    ok = rd["operaciones"] > 1 and rd["profit_factor"] > 1 and rd["media_$"] > 0 and rd["t"] >= 2 and ro.get("profit_factor", 0) > 1
    anual = ops.groupby(pd.DatetimeIndex(ops.t_entrada).year).apply(lambda g: pd.Series(metricas(g))).drop(
        columns=["drawdown_max_$", "racha_perdedora"], errors="ignore")
    SALIDA.mkdir(parents=True)
    ops.to_csv(SALIDA / "trades.csv", index=False)
    tabla.to_csv(SALIDA / "summary.csv", index=False)
    anual.to_csv(SALIDA / "yearly.csv")
    veredicto = "PASA" if ok else "RECHAZADA"
    (SALIDA / "README.md").write_text("\n".join([
        f"# {p.VERSION} (1 MGC + 1 SIL, 16 $ de costes por operación)", "",
        f"Datos: {d.index[0].date()} → {d.index[-1].date()}. Corte fuera de muestra: {corte.date()}.", "",
        tabla.to_markdown(index=False), "", "Por año (fecha de entrada):", "", anual.to_markdown(), "",
        "Motivos de salida: " + str(ops.motivo.value_counts().to_dict()), "", f"**Veredicto: {veredicto}**"]),
        encoding="utf-8")
    print(tabla.to_string(index=False))
    print(anual.to_string())
    print("Motivos:", ops.motivo.value_counts().to_dict())
    print("Veredicto:", veredicto)


if __name__ == "__main__":
    main()
