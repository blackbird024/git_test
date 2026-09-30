"""CLI del motor de producción de "Primera Versión".

Comandos implementados (todos funcionan; los que faltan se añadirán cuando funcionen de verdad):
  niche                       Puntuación de nichos de la Fase 1 y sensibilidad a los pesos.
  brand-preview               Paleta, logo, miniatura de ejemplo y banner en reports/marca/.
  ideas list [--estado E]     Lista los temas de data/topics/.
  ideas show T0001            Ficha completa de un tema.
  ideas new "Título" "Pregunta central"
  ideas state T0001 CAMPO VALOR [--nota N]   Cambia estado_investigacion o estado_produccion (con historial).
  ideas validate              Comprueba todas las fichas.
  project new T0001           Crea la carpeta del vídeo (projects/V####) con su manifiesto.
  project status [V0001]      Estado de los proyectos y de sus pasos.
"""
import argparse
import sys

import yaml

from src.branding import preview
from src.core import projects
from src.core.logs import evento, logger
from src.ideation import topics
from src.research import niche_scoring

LOG = logger("cli")


def cmd_niche(_a) -> int:
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


def cmd_brand_preview(_a) -> int:
    for p in preview.generar():
        print(p.relative_to(preview.RAIZ))
    return 0


def cmd_ideas(a) -> int:
    if a.accion == "list":
        ts = [t for t in topics.todos() if not a.estado or a.estado in (t["estado_investigacion"], t["estado_produccion"])]
        print(f"{'ID':<6} {'Investigación':<17} {'Producción':<11} {'Fuentes':>7}  Título")
        for t in ts:
            print(f"{t['id']:<6} {t['estado_investigacion']:<17} {t['estado_produccion']:<11} {len(t['evidencia']):>7}  "
                  f"{t['titulo_trabajo']}")
    elif a.accion == "show":
        print(yaml.safe_dump(topics.cargar(a.args[0]), allow_unicode=True, sort_keys=False, width=110))
    elif a.accion == "new":
        t = topics.nuevo(a.args[0], a.args[1])
        evento(LOG, "tema creado", id=t["id"])
        print(f"Creado {t['id']}: data/topics/{t['id']}.yaml (complétalo antes de investigar)")
    elif a.accion == "state":
        tid, campo, valor = a.args
        t = topics.cambiar_estado(tid, campo, valor, a.nota or "")
        evento(LOG, "estado cambiado", id=tid, campo=campo, valor=valor)
        print(f"{tid}: {t['historial'][-1]['cambio']}")
    elif a.accion == "validate":
        print(f"{len(topics.todos())} temas válidos")
    return 0


def cmd_project(a) -> int:
    if a.accion == "new":
        m = projects.crear(a.id)
        evento(LOG, "proyecto creado", id=m["id"], tema=m["tema"])
        print(f"Creado {m['id']} para {m['tema']}: projects/{m['id']}/")
    else:
        ms = [projects.cargar(a.id)] if a.id else [projects.store.leer(p) for p in sorted(projects.PROYECTOS.glob("V*/manifest.yaml"))]
        if not ms:
            print("No hay proyectos.")
        for m in ms:
            pasos = ", ".join(f"{k}={v['estado']}" for k, v in m["pasos"].items()) or "sin pasos"
            print(f"{m['id']}  {m['tema']}  {m['titulo_trabajo']}  |  {pasos}  |  aprobación guion: "
                  f"{m['aprobaciones']['guion'] or 'pendiente'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="main.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("niche", help="puntuación de nichos (Fase 1)").set_defaults(func=cmd_niche)
    sub.add_parser("brand-preview", help="vista previa de la identidad visual (Fase 2)").set_defaults(func=cmd_brand_preview)
    p = sub.add_parser("ideas", help="base de temas (Fase 3)")
    p.add_argument("accion", choices=["list", "show", "new", "state", "validate"])
    p.add_argument("args", nargs="*")
    p.add_argument("--estado")
    p.add_argument("--nota")
    p.set_defaults(func=cmd_ideas)
    p = sub.add_parser("project", help="proyectos de vídeo")
    p.add_argument("accion", choices=["new", "status"])
    p.add_argument("id", nargs="?")
    p.set_defaults(func=cmd_project)
    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except (topics.ErrorTema, projects.ErrorProyecto, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
