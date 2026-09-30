"""CLI del motor de producción para YouTube.

Comandos implementados:
  python main.py niche          Puntúa las categorías de la Fase 1 y muestra la sensibilidad a los pesos.
  python main.py brand-preview  Dibuja paleta, logo, miniatura de ejemplo y banner en reports/marca/.

El resto de comandos (research, ideas, script, storyboard, produce, quality-check, package, analytics, report)
se añadirán etapa por etapa, cada uno solo cuando funcione de verdad.
"""
import argparse
import sys

from src.branding import preview
from src.research import niche_scoring


def cmd_niche(_args) -> int:
    pesos, datos = niche_scoring.cargar()
    res = niche_scoring.puntuar(pesos, datos)
    sens = niche_scoring.sensibilidad(pesos, datos)
    print(f"{'Categoría':<52} {'Puntos':>6} {'%juicio':>8} {'1º (±20% pesos)':>16} {'puesto medio':>13}")
    for r in res:
        s = sens[r.clave]
        print(f"{r.nombre:<52} {r.puntuacion:>6.1f} {r.pct_juicio:>7.0f}% {s['primero_%']:>15.1f}% {s['puesto_medio']:>13.2f}")
    print("\n'%juicio' = parte del peso que descansa en valoración propia sin fuente. La puntuación compara opciones; "
          "no predice el éxito.")
    return 0


def cmd_brand_preview(_args) -> int:
    for p in preview.generar():
        print(p.relative_to(preview.RAIZ))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="main.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("niche", help="puntuación de nichos (Fase 1)").set_defaults(func=cmd_niche)
    sub.add_parser("brand-preview", help="vista previa de la identidad visual (Fase 2)").set_defaults(func=cmd_brand_preview)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
