"""Rutas del proyecto y carga de configuración. Los secretos solo se leen de variables de entorno."""
import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
TEMAS = RAIZ / "data" / "topics"
PROYECTOS = RAIZ / "projects"
LOGS = RAIZ / "logs"


def canal() -> dict:
    return yaml.safe_load((RAIZ / "config" / "channel.yaml").read_text())


def secreto(nombre: str) -> str | None:
    """Devuelve el valor de una variable de entorno o None. Nunca se registra en logs ni se imprime."""
    v = os.environ.get(nombre, "").strip()
    return v or None
