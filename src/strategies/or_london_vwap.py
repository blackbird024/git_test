"""OR_LONDON_VWAP_v1.0: ruptura del rango 09:30-10:00 NY a favor de Londres y del VWAP (reglas en edges/or_london_vwap.md).

Solo detecta señales y simula con el motor estándar; nunca ejecuta órdenes.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, ejecutar
from src.horas import NUEVA_YORK, hora_local_a_utc
from src.strategies.mnq_or_vwap import vwap_sesion

VERSION = "OR_LONDON_VWAP_v1.0"


@dataclass(frozen=True)
class Config:
    londres: tuple = ("03:00", "09:30")
    apertura: str = "09:30"
    fin_rango: str = "10:00"
    ultima_senal: str = "15:50"          # la vela de 5M de señal debe cerrar antes
    salida_tiempo: str = "15:55"
    objetivo_r: float = 2.0
    filtro_londres: bool = True          # False solo como control del informe
    tick: float = 0.25
    valor_punto: float = 2.0             # MNQ
    contratos: int = 1
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def senal(dia: pd.DataFrame, fecha, cfg: Config) -> dict:
    """Primera señal del día usando solo velas cerradas. `dia` = velas de 1M de 03:00 a 16:00 NY."""
    t = lambda h: hora_local_a_utc(fecha, h, NUEVA_YORK)  # noqa: E731
    idx = dia.index
    lon = dia[(idx >= t(cfg.londres[0])) & (idx < t(cfg.londres[1]))]
    if lon.empty:
        return {"estado": "sin_londres"}
    rth = dia[idx >= t(cfg.apertura)]
    rango = rth[rth.index < t(cfg.fin_rango)]
    if len(rango) < 30:
        return {"estado": "rango_incompleto"}
    rh, rl, lh, ll = rango.high.max(), rango.low.min(), lon.high.max(), lon.low.min()
    vw = vwap_sesion(rth).to_numpy()
    C, ix = rth.close.to_numpy(), rth.index
    minuto = ix.tz_convert(NUEVA_YORK).minute.to_numpy()
    # Cierre de vela de 5M = cierre de su última vela de 1M (minutos :04, :09, ...), dentro de la ventana de señal.
    cierres_5m = np.flatnonzero((minuto % 5 == 4) & (ix >= t(cfg.fin_rango)) & (ix + pd.Timedelta(minutes=1) <= t(cfg.ultima_senal)))
    for j in cierres_5m:
        arriba = C[j] > rh and C[j] > vw[j] and (C[j] > lh or not cfg.filtro_londres)
        abajo = C[j] < rl and C[j] < vw[j] and (C[j] < ll or not cfg.filtro_londres)
        if arriba or abajo:
            return {"estado": "senal", "t": ix[j], "direccion": 1 if arriba else -1, "rh": rh, "rl": rl}
    return {"estado": "sin_senal"}


def operar_dia(dia: pd.DataFrame, fecha, cfg: Config):
    s = senal(dia, fecha, cfg)
    if s["estado"] != "senal":
        return s["estado"], None
    j, d = int(dia.index.get_loc(s["t"])), s["direccion"]
    if j + 1 >= len(dia):
        return "sin_vela_de_entrada", None
    entrada = dia.open.iloc[j + 1] + d * cfg.costes.ticks(dia.index[j + 1]) * cfg.tick
    stop = s["rl"] if d == 1 else s["rh"]
    r = (entrada - stop) * d
    if r <= 0:
        return "entrada_mas_alla_del_stop", None
    op = ejecutar(dia, j, d, stop, entrada + d * cfg.objetivo_r * r, cfg.contratos,
                  hora_local_a_utc(fecha, cfg.salida_tiempo, NUEVA_YORK), cfg.tick, cfg.valor_punto, cfg.costes)
    if op is None:
        return "sin_vela_de_entrada", None
    op.riesgo_usd = abs(op.entrada - stop) * cfg.valor_punto * cfg.contratos     # 1R = distancia al stop
    return "operada", op


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()):
    ny = m1.index.tz_convert(NUEVA_YORK)
    tramo = m1[(ny.hour >= 3) & (ny.hour < 16)]
    ops, estados = [], {}
    for f, dia in tramo.groupby(tramo.index.tz_convert(NUEVA_YORK).date):
        if f in excluir or pd.Timestamp(f).weekday() >= 5:
            continue
        estado, op = operar_dia(dia, f, cfg)
        estados[estado] = estados.get(estado, 0) + 1
        if op is not None:
            ops.append(op)
    return a_tabla(ops), estados


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion})
