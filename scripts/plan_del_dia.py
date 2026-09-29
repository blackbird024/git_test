"""Plan del día de la cartera NQ (zona de ruido + RSI(2)). NUNCA envía órdenes.

Uso:
  python scripts/plan_del_dia.py                      # antes de las 15:30 (Italia): actualiza datos y muestra todo
  python scripts/plan_del_dia.py --apertura 30512.25  # a las 15:30: añade las bandas de la zona de ruido de hoy
Opciones: --sin-descarga, --confirmar (descarga de más de 0,50 $),
          --telegram (envía el plan a tu bot; necesita TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el entorno).
Plan completo: PLAN_OPERATIVO.md
"""
import argparse
import contextlib
import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts import senal_hoy, zona_ruido_hoy  # noqa: E402
from src.alerts import telegram  # noqa: E402


def capturar(funcion, argv):
    """Ejecuta `funcion` con esos argumentos, la muestra en consola y devuelve el texto."""
    sys.argv = argv
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        funcion()
    texto = buf.getvalue()
    print(texto)
    return texto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apertura", type=float)
    ap.add_argument("--sin-descarga", action="store_true")
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--telegram", action="store_true")
    a = ap.parse_args()
    if not a.sin_descarga:
        senal_hoy.actualizar(a.confirmar)
    print("\n#################### 1) ZONA DE RUIDO (intradía, 16:00-22:00 Italia) ####################")
    zona = capturar(zona_ruido_hoy.main, ["zona_ruido_hoy", "--sin-descarga"]
                    + (["--apertura", str(a.apertura)] if a.apertura else []))
    print("\n#################### 2) RSI(2) (swing; la orden es para la reapertura de las 00:00 Italia) ####################")
    rsi = capturar(senal_hoy.main, ["senal_hoy", "--sin-descarga"])
    print("\nAnota todo en papel/registro.csv. Nada de esto envía órdenes.")
    if a.telegram:
        # Solo lo esencial: la tabla de bandas (sin el texto de ayuda) y la acción del RSI(2)
        tabla = zona.split("QUÉ HACER")[0].strip()
        accion = [l for l in rsi.splitlines() if l.startswith((">>>", "POSICIÓN", "Última sesión", "RSI(2) ="))]
        telegram.enviar("📊 ZONA DE RUIDO — plan de hoy\n" + tabla, monoespaciado=True)
        telegram.enviar("📈 RSI(2) NQ\n" + "\n".join(accion) + "\n\n(Solo aviso: las órdenes las pones tú.)")


if __name__ == "__main__":
    main()
