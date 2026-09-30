"""Registro estructurado: una línea JSON por evento en logs/engine.jsonl, y un resumen legible en consola."""
import json
import logging
from datetime import datetime, timezone

from src.core.config import LOGS


class _Json(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "nivel": r.levelname,
             "modulo": r.name, "evento": r.getMessage()}
        d.update(getattr(r, "datos", {}))
        return json.dumps(d, ensure_ascii=False, default=str)


def logger(nombre: str) -> logging.Logger:
    lg = logging.getLogger(nombre)
    if not lg.handlers:
        LOGS.mkdir(exist_ok=True)
        f = logging.FileHandler(LOGS / "engine.jsonl", encoding="utf-8")
        f.setFormatter(_Json())
        lg.addHandler(f)
        lg.setLevel(logging.INFO)
        lg.propagate = False
    return lg


def evento(lg: logging.Logger, mensaje: str, **datos) -> None:
    lg.info(mensaje, extra={"datos": datos})
