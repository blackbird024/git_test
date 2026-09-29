"""Ventaja 2 — Oro: comprar al cierre de la última sesión de la semana y vender al cierre de la primera
de la semana siguiente (reglas en edges/oro_fin_de_semana.md).

Es una regla de calendario (no usa precios para decidir). "Cierre" = apertura del último minuto de la
sesión de CME (antes de las 17:00 de Nueva York). Para comparar, se calcula lo mismo para TODOS los pares
de sesiones consecutivas: si el viernes->lunes no es mejor que un día cualquiera, no hay efecto propio.
Se descartan los pares que cruzan un cambio de contrato (los precios serían de vencimientos distintos).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data.datos import sesiones
from src.engine.costes import Costes

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass(frozen=True)
class Config:
    tick: float = 0.10
    valor_punto: float = 10.0        # MGC
    contratos: int = 1
    costes: Costes = Costes()


def pares(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()) -> pd.DataFrame:
    """Una fila por par de sesiones consecutivas (compra al cierre de una, venta al cierre de la siguiente)."""
    s = sesiones(m1)
    vol20 = s.ret.rolling(20, min_periods=10).std().shift(1)        # volatilidad diaria conocida de antemano
    filas = []
    fechas = list(s.index)
    for a, b in zip(fechas[:-1], fechas[1:]):
        if a.date() in excluir or b.date() in excluir:
            continue
        ea, eb = s.loc[a], s.loc[b]
        if eb.primer_id != ea.ultimo_id or eb.ultimo_id != ea.ultimo_id:
            continue                                              # cruza un cambio de contrato
        c = cfg.costes
        entrada = ea.open_ultima + c.ticks(ea.t_ultima) * cfg.tick
        salida = eb.open_ultima - c.ticks(eb.t_ultima) * cfg.tick
        pv = cfg.valor_punto * cfg.contratos
        neto = (salida - entrada) * pv - c.comision(cfg.contratos)
        ret = salida / entrada - 1
        filas.append({
            "sesion_entrada": a, "dia_entrada": DIAS[a.weekday()], "t_entrada": ea.t_ultima,
            "fin_de_semana": a.isocalendar().week != b.isocalendar().week,
            "ret_%": ret * 100, "neto": neto,
            "r": ret / vol20.loc[a] if vol20.loc[a] > 0 else np.nan,
            "hueco_%": (eb.open / ea.open_ultima - 1) * 100,              # cierre -> reapertura
            "sesion_siguiente_%": (eb.open_ultima / eb.open - 1) * 100,   # reapertura -> cierre
        })
    return pd.DataFrame(filas).dropna(subset=["r"])


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()) -> pd.DataFrame:
    p = pares(m1, cfg, excluir)
    return p[p.fin_de_semana].reset_index(drop=True)
