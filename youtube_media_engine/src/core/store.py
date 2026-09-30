"""Persistencia en ficheros YAML legibles (un fichero por registro), versionados en git.

Por qué no SQLite: cada sesión en la nube empieza con un contenedor vacío; git es lo único que persiste, y un YAML
por registro deja un historial revisable. La escritura es atómica (fichero temporal + rename).
"""
import os
import tempfile
from pathlib import Path

import yaml


def leer(ruta: Path) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(datos, f, allow_unicode=True, sort_keys=False, width=120)
        os.replace(tmp, ruta)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def siguiente_id(carpeta: Path, prefijo: str, digitos: int = 4) -> str:
    nums = [int(p.stem[len(prefijo):]) for p in carpeta.glob(f"{prefijo}*.yaml") if p.stem[len(prefijo):].isdigit()]
    return f"{prefijo}{(max(nums) + 1 if nums else 1):0{digitos}d}"
