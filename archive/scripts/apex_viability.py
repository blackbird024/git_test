"""Análisis de viabilidad: ¿qué ventaja y qué riesgo por operación hacen falta para aprobar Apex EOD?

Simula 20.000 evaluaciones por combinación con operaciones inventadas: cada una gana +1,5R o
pierde -1R, con la probabilidad de acierto que da la expectativa pedida (ya descontados costes).
30 días naturales ≈ 21 días de trading.

Uso: python scripts/apex_viability.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_system  # noqa: E402
from src.validation.monte_carlo import simulate_paths, synthetic_days  # noqa: E402

EXPECTANCIES = (0.0, 0.05, 0.10, 0.20, 0.30)
RISKS = (150, 250, 400, 600)
TRADES_PER_DAY = (1, 2)
PATHS, DAYS = 20_000, 21


def main() -> None:
    _, account = load_system()
    rows = []
    for tpd in TRADES_PER_DAY:
        for e in EXPECTANCIES:
            for risk in RISKS:
                pnl, worst = synthetic_days(e, risk, PATHS, DAYS, trades_per_day=tpd)
                r = simulate_paths(pnl, worst, account)
                rows.append({"ops/día": tpd, "expectativa (R)": e, "riesgo/op ($)": risk,
                             "aprobadas %": r["% aprobadas"], "suspendidas %": r["% suspendidas"],
                             "caducadas %": r["% caducadas"]})
    table = pd.DataFrame(rows)
    out = Path(__file__).resolve().parent.parent / "reports" / "apex_viabilidad.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Viabilidad de la evaluación Apex EOD 50K\n\n")
        f.write(f"{PATHS:,} evaluaciones simuladas por fila, {DAYS} días de trading, "
                "ganancia +1,5R / pérdida -1R.\n\n")
        for tpd in TRADES_PER_DAY:
            f.write(f"## {tpd} operación(es) al día\n\n")
            sub = table[table["ops/día"] == tpd].drop(columns="ops/día")
            f.write(sub.to_markdown(index=False) + "\n\n")
    print(table.to_string(index=False))
    print(f"\nGuardado en {out}")


if __name__ == "__main__":
    main()
