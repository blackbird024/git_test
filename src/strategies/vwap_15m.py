"""VWAP_15M_2R_v1.0: cruce del VWAP de sesión en velas de 15 min, stop en la vela de señal, objetivo 2R.
Reglas en edges/vwap_15m_2r.md. Solo simula; nunca ejecuta órdenes.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, ejecutar
from src.horas import NUEVA_YORK, hora_local_a_utc
from src.strategies.mnq_or_vwap import vwap_sesion

VERSION = "VWAP_15M_2R_v1.0"


@dataclass(frozen=True)
class Config:
    minutos_vela: int = 15
    ultima_senal_min: int = 330          # la vela de señal debe cerrar como tarde a las 15:00 NY (330 min desde 09:30)
    salida_tiempo: str = "15:55"
    objetivo_r: float = 2.0
    tick: float = 0.25
    valor_punto: float = 2.0             # MNQ
    contratos: int = 1
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def velas(dia: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Velas de 15 min de la sesión con la posición (en `dia`) de su última vela de 1M y el VWAP a su cierre."""
    ny = dia.index.tz_convert(NUEVA_YORK)
    minuto = (ny.hour - 9) * 60 + ny.minute - 30
    vw = vwap_sesion(dia).to_numpy()
    g = pd.DataFrame({"vela": minuto // cfg.minutos_vela, "pos": np.arange(len(dia)), "high": dia.high.to_numpy(),
                      "low": dia.low.to_numpy(), "close": dia.close.to_numpy(), "vwap": vw}).groupby("vela")
    v = pd.DataFrame({"pos": g.pos.last(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "vwap": g.vwap.last()})
    v["cierre_min"] = (v.index + 1) * cfg.minutos_vela
    return v


def operar_dia(dia: pd.DataFrame, fecha, cfg: Config):
    v = velas(dia, cfg)
    t_salida = hora_local_a_utc(fecha, cfg.salida_tiempo, NUEVA_YORK)
    ops, libre_desde = [], None                  # instante desde el que se puede buscar una nueva señal
    arriba = (v.close > v.vwap).to_numpy()
    for k in range(1, len(v)):
        if v.cierre_min.iloc[k] > cfg.ultima_senal_min:
            break
        if v.index[k] - v.index[k - 1] != 1:     # velas no consecutivas (hueco de datos): no hay cruce definido
            continue
        j = int(v.pos.iloc[k])
        if libre_desde is not None and dia.index[j] < libre_desde:
            continue
        if arriba[k] == arriba[k - 1]:
            continue
        d = 1 if arriba[k] else -1
        if j + 1 >= len(dia):
            break
        entrada = dia.open.iloc[j + 1] + d * cfg.costes.ticks(dia.index[j + 1]) * cfg.tick
        stop = v.low.iloc[k] if d == 1 else v.high.iloc[k]
        r = (entrada - stop) * d
        if r <= 0:
            continue
        op = ejecutar(dia, j, d, stop, entrada + d * cfg.objetivo_r * r, cfg.contratos, t_salida,
                      cfg.tick, cfg.valor_punto, cfg.costes)
        if op is None:
            continue
        op.riesgo_usd = abs(op.entrada - stop) * cfg.valor_punto * cfg.contratos     # 1R = distancia al stop
        ops.append(op)
        libre_desde = op.t_salida
    return ops


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()):
    ny = m1.index.tz_convert(NUEVA_YORK)
    rth = m1[(ny.hour * 60 + ny.minute >= 570) & (ny.hour < 16)]
    ops, dias = [], 0
    for f, dia in rth.groupby(rth.index.tz_convert(NUEVA_YORK).date):
        if f in excluir or pd.Timestamp(f).weekday() >= 5:
            continue
        dias += 1
        ops.extend(operar_dia(dia, f, cfg))
    return a_tabla(ops), dias


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion})
