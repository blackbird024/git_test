"""Plan del día de la cartera NQ (zona de ruido + RSI(2)). NUNCA envía órdenes.

Uso:
  python scripts/plan_del_dia.py                      # antes de las 15:30 (Italia): actualiza datos y muestra todo
  python scripts/plan_del_dia.py --apertura 30512.25  # a las 15:30: añade las bandas de la zona de ruido de hoy
Opciones: --sin-descarga, --confirmar (descarga de más de 0,50 $).
Plan completo: PLAN_OPERATIVO.md
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts import senal_hoy, zona_ruido_hoy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apertura", type=float)
    ap.add_argument("--sin-descarga", action="store_true")
    ap.add_argument("--confirmar", action="store_true")
    a = ap.parse_args()
    if not a.sin_descarga:
        senal_hoy.actualizar(a.confirmar)
    print("\n#################### 1) ZONA DE RUIDO (intradía, 16:00-22:00 Italia) ####################")
    sys.argv = ["zona_ruido_hoy", "--sin-descarga"] + (["--apertura", str(a.apertura)] if a.apertura else [])
    zona_ruido_hoy.main()
    print("\n#################### 2) RSI(2) (swing; la orden es para la reapertura de las 00:00 Italia) ####################")
    sys.argv = ["senal_hoy", "--sin-descarga"]
    senal_hoy.main()
    print("\nAnota todo en papel/registro.csv. Nada de esto envía órdenes.")


if __name__ == "__main__":
    main()
