"""Alertas de GOLD_SWING_SIMPLE_v1.0: imprime las señales recientes y las guarda en un CSV. NUNCA ejecuta órdenes.

Uso:  python scripts/senales_oro.py [--hasta AAAA-MM-DD] [--dias 5]
  --hasta  usa solo datos anteriores a esa fecha (por defecto, todos los disponibles).
Aviso: la v1.0 NO superó el desarrollo (reports/GOLD_SWING_SIMPLE_v1.0). Estas alertas son solo informativas.
Los precios son del contrato GC de ese momento; para XAUUSD aplica la diferencia de base (las distancias no cambian).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data.datos import velas_1m  # noqa: E402
from src.strategies import gold_swing_simple as g  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hasta")
    ap.add_argument("--dias", type=int, default=5)
    a = ap.parse_args()
    m1 = velas_1m("GC")
    if a.hasta:
        m1 = m1[m1.index < pd.Timestamp(a.hasta, tz="UTC")]
    ops, _ = g.backtest(m1, g.Config())
    desde = m1.index.max() - pd.Timedelta(days=a.dias)
    recientes = ops[ops.t_entrada >= desde] if len(ops) else ops
    if recientes.empty:
        print(f"Sin señales en los últimos {a.dias} días (datos hasta {m1.index.max():%Y-%m-%d %H:%M} UTC).")
        return
    salida = Path(__file__).resolve().parent.parent / "reports" / "senales_oro.csv"
    recientes[["t_entrada", "lado", "entrada_real", "sl_real", "tp_real", "resultado"]].to_csv(
        salida, mode="a", header=not salida.exists(), index=False)
    for _, op in recientes.iterrows():
        print(g.alerta(op), "\n")


if __name__ == "__main__":
    main()
