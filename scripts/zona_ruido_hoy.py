"""Herramienta diaria de ZONA_RUIDO_MNQ_v1.0 (papel / demo). NUNCA envía órdenes.

Uso:
  1) La víspera o por la mañana:  python scripts/zona_ruido_hoy.py
     → cierre de ayer y el % de "ruido normal" de cada media hora.
  2) A las 15:30 de Italia (apertura de NY), con el precio de apertura del gráfico:
     python scripts/zona_ruido_hoy.py --apertura 21450.25
     → tabla con la banda superior e inferior de cada media hora, en hora de Italia.
Opciones: --sin-descarga (no actualiza datos de Databento), --confirmar (permite una descarga de más de 0,50 $).
Reglas completas: edges/zona_ruido_mnq.md. Registro de la prueba: papel/zona_ruido_registro.csv.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.data.calidad import limpiar  # noqa: E402
from src.data.cargadores import cargar_databento  # noqa: E402
from src.horas import NUEVA_YORK, ROMA, hora_local_a_utc  # noqa: E402
from src.strategies import zona_ruido as z  # noqa: E402


def siguiente_dia_habil(fecha):
    d = pd.Timestamp(fecha) + pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d += pd.Timedelta(days=1)
    return d.date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apertura", type=float, help="precio de apertura de las 09:30 NY (15:30 Italia)")
    ap.add_argument("--sin-descarga", action="store_true")
    ap.add_argument("--confirmar", action="store_true")
    a = ap.parse_args()
    if not a.sin_descarga:
        from scripts.senal_hoy import actualizar
        actualizar(a.confirmar)
    m1 = limpiar(cargar_databento("NQ"))
    cfg = z.Config()
    n = z.niveles(m1, a.apertura, cfg)
    hoy = siguiente_dia_habil(n["ultima_sesion"])
    t = n["tabla"].copy()
    hhmm = [f"{9 + (30 + m) // 60}:{(30 + m) % 60:02d}" for m in t.chequeo_min]
    t.insert(0, "hora_italia", [f"{hora_local_a_utc(hoy, h, NUEVA_YORK).tz_convert(ROMA):%H:%M}" for h in hhmm])
    t.insert(1, "hora_NY", hhmm)
    t = t.drop(columns="chequeo_min")
    print(f"\n============ {z.VERSION} — sesión del {hoy:%d-%m-%Y} ============")
    print(f"Datos hasta la sesión del {n['ultima_sesion']:%d-%m-%Y}. Cierre de ayer (16:00 NY): {n['cierre_anterior']:,.2f}")
    if a.apertura is None:
        print("\n'Ruido normal' de cada media hora (sigma, % desde la apertura):")
        print(t.to_string(index=False, formatters={"sigma_%": "{:.3f}".format}))
        print("\nA las 15:30 de Italia, vuelve a ejecutar con --apertura PRECIO para tener las bandas.")
        print("  banda superior = max(apertura, cierre de ayer) x (1 + sigma)")
        print("  banda inferior = min(apertura, cierre de ayer) x (1 - sigma)")
    else:
        print(f"Apertura de hoy: {a.apertura:,.2f}\n")
        print(t.to_string(index=False, formatters={"sigma_%": "{:.3f}".format, "banda_sup": "{:,.2f}".format,
                                                   "banda_inf": "{:,.2f}".format}))
    print("""
QUÉ HACER EN CADA HORA DE LA TABLA (mira el cierre de la vela de 1 minuto anterior):
  - Sin posición: por encima de la banda superior → COMPRAR 1 MNQ; por debajo de la inferior → VENDER 1 MNQ.
  - Comprado: si el precio está por debajo de max(banda superior, VWAP) → CERRAR
    (y si además está bajo la banda inferior → VENDER).
  - Vendido: simétrico, con min(banda inferior, VWAP).
  - A las 22:00 de Italia (16:00 NY): cerrar todo.
VWAP: el de la sesión que empieza a las 09:30 NY (en TradingView, 'VWAP' con anclaje de sesión y solo horario
regular). Anota cada operación en papel/zona_ruido_registro.csv. Este script NUNCA envía órdenes.""")


if __name__ == "__main__":
    main()
