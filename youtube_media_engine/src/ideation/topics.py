"""Base de oportunidades de contenido (Fase 3): un YAML por tema en data/topics/T####.yaml.

Reglas que se comprueban:
  - todos los campos de la ficha existen y los enumerados tienen valores válidos;
  - un tema no pasa de 'sin_investigar' sin al menos una fuente con URL;
  - un tema no entra en producción sin estar 'investigado';
  - cada cambio de estado queda en el historial con fecha.
"""
from datetime import date
from pathlib import Path

from src.core import store
from src.core.config import TEMAS

CAMPOS = ["id", "titulo_trabajo", "pregunta_central", "audiencia", "formato", "duracion_min", "gancho",
          "estructura", "recompensa", "angulo_original", "evidencia", "complejidad", "riesgos",
          "por_que_atrae", "miniatura", "tipo_oportunidad", "categoria", "estado_investigacion",
          "estado_produccion", "historial"]
FORMATOS = {"corto", "documental_corto", "documental_largo", "explicador", "actualidad"}
TIPOS = {"evergreen", "tendencia", "estacional", "hueco"}
COMPLEJIDAD = {"baja", "media", "alta"}
INVESTIGACION = ["sin_investigar", "en_investigacion", "investigado", "descartado"]
PRODUCCION = ["idea", "guion", "storyboard", "produccion", "revision", "listo", "publicado", "archivado"]


class ErrorTema(ValueError):
    pass


def ruta(tid: str, carpeta: Path = TEMAS) -> Path:
    return carpeta / f"{tid}.yaml"


def validar(t: dict) -> None:
    faltan = [c for c in CAMPOS if c not in t]
    if faltan:
        raise ErrorTema(f"{t.get('id', '?')}: faltan campos {faltan}")
    tid = t["id"]
    for campo, valores in (("formato", FORMATOS), ("tipo_oportunidad", TIPOS), ("complejidad", COMPLEJIDAD),
                           ("estado_investigacion", INVESTIGACION), ("estado_produccion", PRODUCCION)):
        if t[campo] not in valores:
            raise ErrorTema(f"{tid}: {campo}='{t[campo]}' no es válido ({sorted(valores)})")
    for e in t["evidencia"]:
        if not e.get("url") or not e.get("titulo"):
            raise ErrorTema(f"{tid}: cada evidencia necesita 'titulo' y 'url'")
    if t["estado_investigacion"] != "sin_investigar" and not t["evidencia"]:
        raise ErrorTema(f"{tid}: '{t['estado_investigacion']}' sin ninguna fuente")
    if t["estado_produccion"] != "idea" and t["estado_investigacion"] != "investigado":
        raise ErrorTema(f"{tid}: no puede estar en '{t['estado_produccion']}' sin estar 'investigado'")


def cargar(tid: str, carpeta: Path = TEMAS) -> dict:
    p = ruta(tid, carpeta)
    if not p.exists():
        raise ErrorTema(f"No existe el tema {tid}")
    t = store.leer(p)
    validar(t)
    return t


def todos(carpeta: Path = TEMAS) -> list[dict]:
    out = []
    for p in sorted(carpeta.glob("T*.yaml")):
        t = store.leer(p)
        validar(t)
        out.append(t)
    return out


def nuevo(titulo: str, pregunta: str, carpeta: Path = TEMAS, hoy: date | None = None) -> dict:
    tid = store.siguiente_id(carpeta, "T")
    t = {c: "" for c in CAMPOS}
    t.update(id=tid, titulo_trabajo=titulo, pregunta_central=pregunta, formato="documental_corto", duracion_min=10,
             evidencia=[], complejidad="media", riesgos=[], tipo_oportunidad="evergreen", categoria="inventos",
             estado_investigacion="sin_investigar", estado_produccion="idea",
             historial=[{"fecha": str(hoy or date.today()), "cambio": "creado"}])
    validar(t)
    store.escribir(ruta(tid, carpeta), t)
    return t


def cambiar_estado(tid: str, campo: str, valor: str, nota: str = "", carpeta: Path = TEMAS,
                   hoy: date | None = None) -> dict:
    if campo not in ("estado_investigacion", "estado_produccion"):
        raise ErrorTema(f"Campo de estado desconocido: {campo}")
    t = cargar(tid, carpeta)
    anterior = t[campo]
    t[campo] = valor
    t["historial"].append({"fecha": str(hoy or date.today()), "cambio": f"{campo}: {anterior} -> {valor}",
                           **({"nota": nota} if nota else {})})
    validar(t)                                   # si el cambio no es válido, no se guarda
    store.escribir(ruta(tid, carpeta), t)
    return t
