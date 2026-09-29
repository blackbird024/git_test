"""Carga de configuración y preparación de datos (con caché en disco para no reconstruir las velas cada vez)."""
from __future__ import annotations

import copy
import hashlib
import json
import pickle
from pathlib import Path

import yaml

from .data_loader import DataQualityError, load_ohlcv, validate_and_clean
from .session_manager import build_bars
from .signals import añadir_indicadores

RAIZ = Path(__file__).resolve().parent.parent


def load_config(ruta: str | Path = RAIZ / "config" / "settings.yaml", overrides: list[str] | None = None) -> dict:
    cfg = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    for o in overrides or []:
        set_path(cfg, *o.split("=", 1))
    return cfg


def set_path(cfg: dict, clave: str, valor, interpretar: bool = True) -> None:
    """set_path(cfg, 'strategy.exits.tp_r', '2.0'); el valor se interpreta como YAML (null, true, 1.5...)."""
    partes = clave.split(".")
    d = cfg
    for p in partes[:-1]:
        d = d[p]
    if partes[-1] not in d:
        raise KeyError(f"Clave desconocida en la configuración: {clave}")
    if interpretar and isinstance(valor, str) and not (len(valor) == 5 and valor[2] == ":"):   # "11:30" es una hora
        valor = yaml.safe_load(valor)
    d[partes[-1]] = valor


def variante(cfg: dict, **cambios) -> dict:
    """Copia de la configuración con cambios {'strategy.exits.tp_r': 2.0, ...} (claves con '__' o '.')."""
    c = copy.deepcopy(cfg)
    for k, v in cambios.items():
        set_path(c, k.replace("__", "."), v, interpretar=False)
    return c


def _clave_cache(cfg: dict) -> str:
    rel = {k: cfg[k] for k in ("data", "session", "bars")}
    return hashlib.sha1(json.dumps(rel, sort_keys=True).encode()).hexdigest()[:12]


def preparar(cfg: dict, usar_cache: bool = True):
    """Devuelve (sesiones, informe_datos). Detiene con DataQualityError si los datos no sirven."""
    cache = RAIZ / "cache" / f"sesiones_{_clave_cache(cfg)}.pkl"
    if usar_cache and cache.exists():
        with open(cache, "rb") as f:
            return pickle.load(f)
    d = cfg["data"]
    bruto = load_ohlcv(d["path"], RAIZ, d["timezone_if_naive"])
    limpio, inf_datos = validate_and_clean(bruto, d["source_bar_minutes"], d["max_invalid_fraction"])
    ses = build_bars(limpio, cfg)
    inf_datos.update(ses.informe)
    if ses.informe["sesiones_validas"] < d["min_sessions"]:
        raise DataQualityError(f"Solo {ses.informe['sesiones_validas']} sesiones válidas (mínimo {d['min_sessions']}).")
    cache.parent.mkdir(exist_ok=True)
    with open(cache, "wb") as f:
        pickle.dump((ses, inf_datos), f)
    return ses, inf_datos


def barras_con_indicadores(ses, cfg: dict):
    cfg = copy.deepcopy(cfg)
    cfg["_vwap_col"] = "vwap_rth" if cfg["session"]["vwap_session"] == "rth" else "vwap_ext"
    return añadir_indicadores(ses.bars, cfg)
