"""Fase 1: control de calidad de los datos descargados.

Comprueba, para la sesión regular (9:30-16:00 ET):
  - cuántos días hay y cuántas velas por día (lo normal son 390);
  - días incompletos (festivos de media jornada o huecos en los datos);
  - cambios de contrato (roll) detectados por el cambio de instrument_id;
  - velas imposibles (máximo < mínimo, precios <= 0).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.loader import load_minutes  # noqa: E402


def check(root: str) -> None:
    df = load_minutes(root)
    rth = df.between_time("09:30", "16:00", inclusive="left")
    per_day = rth.groupby(rth.index.date).size()
    bad = rth[(rth.high < rth.low) | (rth.low <= 0)]
    rolls = (df.instrument_id != df.instrument_id.shift()).sum() - 1

    print(f"\n=== {root} ===")
    print(f"Desde {df.index.min()} hasta {df.index.max()}")
    print(f"Velas totales (24h): {len(df):,} | velas en sesión regular: {len(rth):,}")
    print(f"Días con sesión regular: {len(per_day):,}")
    print(f"Velas por día: mediana {per_day.median():.0f}, mínimo {per_day.min()}")
    print(f"Días con menos de 380 velas: {(per_day < 380).sum()} "
          f"(menos de 300: {(per_day < 300).sum()}, típicamente medias jornadas)")
    print(f"Cambios de contrato detectados: {rolls}")
    print(f"Velas imposibles: {len(bad)}")
    short = per_day[per_day < 300]
    if len(short):
        print("Ejemplos de días cortos:", ", ".join(str(d) for d in short.index[:8]))


if __name__ == "__main__":
    for root in ("NQ", "GC"):
        check(root)
