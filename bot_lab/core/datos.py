"""Contexto de datos del laboratorio: arrays de 1 minuto de NQ, sesiones, partición y velas de 5/15 minutos.

Reutiliza `src.data.datos` (mismos datos procesados y mismas sesiones ilíquidas excluidas que el resto del proyecto).

Ajuste por cambio de contrato (solo para indicadores): `desfase[i]` = suma de los saltos de precio en los cambios de
contrato ANTERIORES o iguales a i (salto = apertura del contrato nuevo - cierre del anterior). El precio ajustado es
precio - desfase: una serie continua que solo usa el pasado. Como el ajuste es aditivo y constante entre cambios,
las comparaciones precio/indicador (EMA, ATR, ADX, RSI) no dependen de él. Los niveles se devuelven a precio real
sumando `desfase` del instante en que se usan.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.datos import excluidos, velas_1m
from src.engine.costes import APERTURAS
from src.horas import en_ventana, sesion_cme

NY = "America/New_York"
RAIZ = Path(__file__).resolve().parents[2]
TRAMOS = ("TRAIN", "VALIDATION", "TEST")


def particion(ruta: Path = RAIZ / "bot_lab" / "configs" / "lab.yaml") -> dict:
    import yaml
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))["particion"]


def tramo_de_fecha(fechas, p: dict | None = None) -> np.ndarray:
    """0 = TRAIN, 1 = VALIDATION, 2 = TEST, según el día NY (sin zona)."""
    p = p or particion()
    f = pd.DatetimeIndex(fechas)
    if f.tz is not None:
        f = f.tz_convert(NY).tz_localize(None).normalize()
    return np.where(f < pd.Timestamp(p["validation_desde"]), 0, np.where(f < pd.Timestamp(p["test_desde"]), 1, 2))


@dataclass
class Velas:
    """Velas de un marco superior. `i1` = posición en el array de 1 min del ÚLTIMO minuto de la vela: la señal
    calculada con esta vela solo se puede ejecutar a partir de i1 + 1."""
    O: np.ndarray
    H: np.ndarray
    L: np.ndarray
    C: np.ndarray
    V: np.ndarray
    Oa: np.ndarray        # ajustados (indicadores)
    Ha: np.ndarray
    La: np.ndarray
    Ca: np.ndarray
    i1: np.ndarray
    i0: np.ndarray        # primer minuto de la vela
    min_ny: np.ndarray    # minuto del día NY del INICIO de la vela
    fecha: np.ndarray     # día NY (datetime64[D])
    ses: np.ndarray       # índice de sesión CME (entero)

    def __len__(self):
        return len(self.C)


class Contexto:
    def __init__(self, m1: pd.DataFrame | None = None, excluir: frozenset | None = None):
        m1 = velas_1m("NQ") if m1 is None else m1
        self.m1 = m1
        self.excluir = excluidos("NQ") if excluir is None else excluir
        idx = m1.index
        self.t = idx
        self.O, self.H, self.L, self.C = (m1[c].to_numpy(float) for c in ("open", "high", "low", "close"))
        self.V = m1.volume.to_numpy(float)
        iid = m1.instrument_id.to_numpy() if "instrument_id" in m1 else np.zeros(len(m1), int)
        cambio = np.r_[False, iid[1:] != iid[:-1]]
        salto = np.where(cambio, self.O - np.r_[self.C[0], self.C[:-1]], 0.0)
        self.desfase = np.cumsum(salto)
        ny = idx.tz_convert(NY)
        self.min_ny = (ny.hour * 60 + ny.minute).to_numpy()
        self.fecha = ny.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
        self.dow = ny.weekday.to_numpy()
        ses_fecha = pd.to_datetime(pd.Series(sesion_cme(idx))).to_numpy().astype("datetime64[D]")
        self.ses_fecha = ses_fecha
        _, self.ses = np.unique(ses_fecha, return_inverse=True)
        self.rth = (self.min_ny >= 570) & (self.min_ny < 960)
        excl = np.array(sorted(pd.Timestamp(d) for d in self.excluir), dtype="datetime64[D]")
        self.excluida = np.isin(ses_fecha, excl)
        self.tramo = tramo_de_fecha(pd.DatetimeIndex(self.fecha))
        abierta = np.zeros(len(idx), bool)
        for zona, a, b in APERTURAS:
            abierta |= en_ventana(idx, a, b, zona)
        self.ticks_desl = np.where(abierta, 2.0, 1.0)

    # ------------------------------------------------------------------ VWAP de 1 minuto
    def _vwap(self, grupo: np.ndarray, activo: np.ndarray):
        tp = (self.H + self.L + self.C) / 3
        v = np.where(activo, self.V, 0.0)
        g = pd.Series(grupo)
        spv = pd.Series(tp * v).groupby(g).cumsum().to_numpy()
        sv = pd.Series(v).groupby(g).cumsum().to_numpy()
        sp2 = pd.Series(tp * tp * v).groupby(g).cumsum().to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            vw = np.where(sv > 0, spv / sv, np.nan)
            var = np.where(sv > 0, sp2 / sv - vw * vw, np.nan)
        vw[~activo] = np.nan
        sd = np.sqrt(np.clip(var, 0, None))
        sd[~activo] = np.nan
        return vw, sd

    @cached_property
    def vwap_rth(self):
        """(vwap, desviación) de la sesión regular hasta el cierre de cada minuto (NaN fuera de 09:30-16:00)."""
        grupo = np.where(self.rth, self.fecha.astype(np.int64), -1)
        return self._vwap(grupo, self.rth)

    @cached_property
    def vwap_globex(self):
        """(vwap, desviación) desde la reapertura de Globex (18:00 NY) hasta el cierre de cada minuto."""
        return self._vwap(self.ses, np.ones(len(self.C), bool))

    def vwap_previo(self, cual: str = "rth") -> np.ndarray:
        """VWAP conocido en la APERTURA de cada minuto (el del cierre del minuto anterior, misma sesión)."""
        vw = (self.vwap_rth if cual == "rth" else self.vwap_globex)[0]
        prev = np.r_[np.nan, vw[:-1]]
        misma = np.r_[False, self.ses[1:] == self.ses[:-1]]
        return np.where(misma, prev, np.nan)

    # ------------------------------------------------------------------ velas de marcos superiores
    def velas(self, minutos: int, solo_rth: bool = False) -> Velas:
        return self._velas(minutos, solo_rth)

    @cached_property
    def _cache_velas(self):
        return {}

    def _velas(self, minutos: int, solo_rth: bool) -> Velas:
        clave = (minutos, solo_rth)
        if clave in self._cache_velas:
            return self._cache_velas[clave]
        cubo = self.t.floor(f"{minutos}min").asi8
        nuevo = np.r_[True, (cubo[1:] != cubo[:-1]) | (self.ses[1:] != self.ses[:-1])]
        ini = np.flatnonzero(nuevo)
        fin = np.r_[ini[1:], len(cubo)] - 1
        a = self.desfase
        O, C = self.O[ini], self.C[fin]
        H = np.maximum.reduceat(self.H, ini)
        L = np.minimum.reduceat(self.L, ini)
        V = np.add.reduceat(self.V, ini)
        # Ajustados: el desfase es constante dentro de una vela salvo en el minuto del cambio (siempre inicio de sesión).
        Oa, Ca = O - a[ini], C - a[fin]
        Ha, La = H - a[fin], L - a[fin]
        ny0 = pd.DatetimeIndex(cubo[ini]).tz_localize("UTC").tz_convert(NY)
        min_ny = (ny0.hour * 60 + ny0.minute).to_numpy()
        v = Velas(O, H, L, C, V, Oa, Ha, La, Ca, fin, ini, min_ny, self.fecha[ini], self.ses[ini])
        if solo_rth:
            k = (min_ny >= 570) & (min_ny < 960)
            v = Velas(*(getattr(v, f)[k] for f in Velas.__dataclass_fields__))
        self._cache_velas[clave] = v
        return v

    # ------------------------------------------------------------------ índices útiles
    def primer_indice_desde(self, fecha: np.datetime64, minuto_ny: int) -> int:
        """Primer minuto con día NY = fecha y minuto NY >= minuto_ny (o -1)."""
        a = np.searchsorted(self.fecha, fecha, side="left")
        b = np.searchsorted(self.fecha, fecha, side="right")
        k = a + np.searchsorted(self.min_ny[a:b], minuto_ny, side="left")
        return int(k) if k < b else -1

    @cached_property
    def indice_dia(self) -> dict:
        """día NY -> (primer, último+1) índice de 1 minuto."""
        f = self.fecha
        cambios = np.r_[0, np.flatnonzero(f[1:] != f[:-1]) + 1, len(f)]
        return {f[cambios[j]]: (cambios[j], cambios[j + 1]) for j in range(len(cambios) - 1)}

    def fin_dia(self, fechas: np.ndarray, minuto_ny: int) -> np.ndarray:
        """Para cada día NY, el primer minuto >= minuto_ny de ese día y anterior a las 18:00 NY (hora de la salida por
        tiempo). Si no existe (cierre anticipado), el último minuto del día antes de las 18:00."""
        out = np.empty(len(fechas), np.int64)
        cache = {}
        for j, d in enumerate(fechas):
            if d not in cache:
                a, b = self.indice_dia.get(d, (0, 0))
                # solo minutos anteriores a las 18:00 NY (a partir de ahí empieza la sesión Globex siguiente)
                b = a + np.searchsorted(self.min_ny[a:b], 1080, side="left") if b > a else b
                if b == a:
                    cache[d] = -1
                else:
                    k = a + np.searchsorted(self.min_ny[a:b], minuto_ny, side="left")
                    cache[d] = k if k < b else b - 1
            out[j] = cache[d]
        return out

    @cached_property
    def sesiones_rth(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(sorted(set(self.fecha[self.rth].tolist()))).normalize()


def cargar_config() -> dict:
    import yaml
    return yaml.safe_load((RAIZ / "bot_lab" / "configs" / "lab.yaml").read_text(encoding="utf-8"))


def guardar_json(obj, ruta: Path):
    ruta.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
