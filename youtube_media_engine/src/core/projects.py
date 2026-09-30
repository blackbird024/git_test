"""Proyectos de vídeo (Fases 5 y 8): una carpeta por vídeo con su manifiesto.

El manifiesto registra cada paso con el hash de sus entradas. Un paso cuyo hash no ha cambiado no se repite, lo
que evita repetir llamadas de pago y publicar dos veces. Así el flujo se puede reanudar en cualquier momento.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core import store
from src.core.config import PROYECTOS
from src.ideation import topics

CARPETAS = ["research", "sources", "script", "storyboard", "audio", "assets", "subtitles", "edit", "render",
            "thumbnail", "qc", "publish", "analytics"]


class ErrorProyecto(ValueError):
    pass


def ruta(vid: str, raiz: Path = PROYECTOS) -> Path:
    return raiz / vid


def crear(tid: str, raiz: Path = PROYECTOS, carpeta_temas: Path | None = None) -> dict:
    kw = {"carpeta": carpeta_temas} if carpeta_temas else {}
    t = topics.cargar(tid, **kw)
    existentes = [store.leer(p) for p in raiz.glob("V*/manifest.yaml")]
    for m in existentes:
        if m["tema"] == tid:
            raise ErrorProyecto(f"El tema {tid} ya tiene el proyecto {m['id']}")
    vid = f"V{len(existentes) + 1:04d}"
    while ruta(vid, raiz).exists():
        vid = f"V{int(vid[1:]) + 1:04d}"
    for c in CARPETAS:
        (ruta(vid, raiz) / c).mkdir(parents=True, exist_ok=True)
    m = {"id": vid, "tema": tid, "titulo_trabajo": t["titulo_trabajo"], "formato": t["formato"],
         "creado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pasos": {},
         "aprobaciones": {"guion": None, "publicacion": None}, "publicado": None}
    store.escribir(ruta(vid, raiz) / "manifest.yaml", m)
    return m


def cargar(vid: str, raiz: Path = PROYECTOS) -> dict:
    p = ruta(vid, raiz) / "manifest.yaml"
    if not p.exists():
        raise ErrorProyecto(f"No existe el proyecto {vid}")
    return store.leer(p)


def huella(*entradas) -> str:
    """Hash estable de las entradas de un paso (textos, dicts o rutas de fichero)."""
    h = hashlib.sha256()
    for e in entradas:
        if isinstance(e, Path):
            h.update(e.read_bytes())
        else:
            h.update(json.dumps(e, sort_keys=True, ensure_ascii=False, default=str).encode())
    return h.hexdigest()[:16]


def hecho(vid: str, paso: str, entradas_hash: str, raiz: Path = PROYECTOS) -> bool:
    p = cargar(vid, raiz)["pasos"].get(paso)
    return bool(p and p["estado"] == "ok" and p["entradas"] == entradas_hash)


def registrar(vid: str, paso: str, entradas_hash: str, estado: str = "ok", raiz: Path = PROYECTOS, **extra) -> dict:
    m = cargar(vid, raiz)
    m["pasos"][paso] = {"estado": estado, "entradas": entradas_hash,
                        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
    store.escribir(ruta(vid, raiz) / "manifest.yaml", m)
    return m
