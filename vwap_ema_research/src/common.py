"""Configuración, preparación de cada instrumento (con caché) y particiones train/validation/test."""
from __future__ import annotations

import copy
import hashlib
import json
import pickle
from pathlib import Path

import pandas as pd
import yaml

from .backtester import run
from .data_loader import DataQualityError, build, inspect_and_clean, load, simbolo_de
from .metrics import summary
from .strategy import features

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path = ROOT / "config" / "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def params(cfg: dict, **cambios) -> dict:
    p = copy.deepcopy(cfg["baseline"])
    for k, v in cambios.items():
        if k not in p:
            raise KeyError(k)
        p[k] = v
    return p


class Lab:
    """Un instrumento: datos preparados, particiones y ejecución de variantes."""

    def __init__(self, cfg: dict, nombre: str):
        self.cfg, self.nombre = cfg, nombre
        self.inst = cfg["instruments"][nombre]
        self.g = cfg["general"]
        self.capital = self.inst.get("capital_override", self.g["initial_capital"])
        self.ses, self.info = self._preparar()
        self.splits = self._particiones()
        self._feat = {}

    def _preparar(self):
        clave = hashlib.sha1(json.dumps([self.inst["data"], self.inst["session"], self.inst["tz"], self.g], sort_keys=True).encode()).hexdigest()[:10]
        cache = ROOT / "results" / "cache" / f"{self.nombre}_{clave}.pkl"
        if cache.exists():
            return pickle.loads(cache.read_bytes())
        df = load(self.inst["data"], ROOT, self.inst.get("data_timezone_if_naive", "UTC"))
        df, info = inspect_and_clean(df, self.g["max_invalid_fraction"], self.nombre)
        info["simbolo_archivo"] = simbolo_de(self.inst["data"])
        ses = build(df, self.inst, self.g)
        info.update(ses.info)
        if ses.info["sesiones_validas"] < self.g["min_sessions"]:
            raise DataQualityError(f"{self.nombre}: solo {ses.info['sesiones_validas']} sesiones válidas.")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps((ses, info)))
        return ses, info

    def _particiones(self) -> dict:
        b = self.ses.bars
        dias = sorted(set(pd.to_datetime(b.session[b.session_valid].astype(str))))
        sp = self.g["split"]
        n = len(dias)
        i1, i2 = int(n * sp["train"]), int(n * (sp["train"] + sp["validation"]))
        return {"train": (dias[0], dias[i1 - 1]), "validation": (dias[i1], dias[i2 - 1]), "test": (dias[i2], dias[-1]),
                "dev": (dias[0], dias[i2 - 1])}

    def features(self, p: dict) -> pd.DataFrame:
        clave = tuple(p[k] for k in ("ema_fast", "ema_medium", "ema_slow", "atr_period", "slope_bars", "structure_bars"))
        if clave not in self._feat:
            self._feat[clave] = features(self.ses.bars, p)
        return self._feat[clave]

    def run(self, p: dict, periodo: str | tuple, slippage_mult: float = 1.0, sig_override=None):
        d, h = self.splits[periodo] if isinstance(periodo, str) else periodo
        r = run(self.features(p), self.ses.sub, p, self.inst, self.capital, d, h, slippage_mult, sig_override)
        return r, summary(r.trades, r.daily, self.capital)


def labs_disponibles(cfg: dict) -> tuple[dict, dict]:
    """Prepara todos los instrumentos con datos; devuelve (labs, faltantes con motivo)."""
    labs, faltan = {}, {}
    for nombre in cfg["instruments"]:
        try:
            labs[nombre] = Lab(cfg, nombre)
        except DataQualityError as e:
            faltan[nombre] = str(e)
    return labs, faltan
