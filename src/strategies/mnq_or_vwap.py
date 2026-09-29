"""MNQ — Opening Range + VWAP (OR_VWAP_v1.0). Reglas en edges/mnq_or_vwap.md.

Separación: este módulo SOLO detecta señales y simula operaciones con el motor estándar. El control de riesgo de
Apex (bloqueos, margen de seguridad) va en un módulo aparte y nunca se mezcla con la estrategia.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, ejecutar
from src.horas import NUEVA_YORK, hora_local_a_utc
from src.risk.position_sizing import contratos

VERSION = "OR_VWAP_v1.0"


@dataclass(frozen=True)
class Config:
    version: str = VERSION
    apertura: str = "09:30"
    fin_rango: str = "09:45"
    ultima_senal: str = "15:54"          # la vela de señal debe empezar antes (entrada como tarde a las 15:54)
    salida_tiempo: str = "15:55"
    objetivo_r: float = 2.0
    tope_puntos: float | None = 40.0     # R máximo en puntos (None = sin tope absoluto)
    tope_pct: float | None = None        # alternativa: R máximo en % del precio de entrada (None = sin tope relativo)
    riesgo_pct: float = 0.005
    saldo_inicial: float = 50_000.0
    tick: float = 0.25
    valor_punto: float = 2.0             # MNQ
    costes: Costes = Costes(comision_lado=1.0, ticks_normal=1, ticks_apertura=1)   # escenario 1: 1 tick

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def vwap_sesion(dia: pd.DataFrame) -> pd.Series:
    """VWAP de la sesión regular: precio típico (H+L+C)/3 ponderado por volumen, acumulado desde las 09:30 NY."""
    tipico = (dia.high + dia.low + dia.close) / 3
    vol = dia.volume.astype(float)
    return (tipico * vol).cumsum() / vol.cumsum().replace(0, np.nan)


def sesion_regular(m1: pd.DataFrame, fecha, cfg: Config) -> pd.DataFrame:
    t0, t1 = hora_local_a_utc(fecha, cfg.apertura, NUEVA_YORK), hora_local_a_utc(fecha, "16:00", NUEVA_YORK)
    return m1[(m1.index >= t0) & (m1.index < t1)]


def senal(dia: pd.DataFrame, fecha, cfg: Config) -> dict:
    """Busca la primera señal del día. Devuelve un dict con `estado` y, si hay señal, sus datos.
    Solo usa velas cerradas hasta la vela de señal (incluida)."""
    t = lambda h: hora_local_a_utc(fecha, h, NUEVA_YORK)  # noqa: E731
    rango = dia[(dia.index >= t(cfg.apertura)) & (dia.index < t(cfg.fin_rango))]
    if len(rango) < 15:
        return {"estado": "rango_incompleto"}
    or_high, or_low = rango.high.max(), rango.low.min()
    vw = vwap_sesion(dia).to_numpy()
    C = dia.close.to_numpy()
    idx = dia.index
    for j in np.flatnonzero((idx >= t(cfg.fin_rango)) & (idx < t(cfg.ultima_senal))):
        largo = C[j] > or_high and C[j] > vw[j]
        corto = C[j] < or_low and C[j] < vw[j]
        if largo or corto:
            return {"estado": "senal", "i": j, "direccion": 1 if largo else -1, "t_senal": idx[j],
                    "or_high": or_high, "or_low": or_low, "vwap": vw[j], "cierre": C[j]}
    return {"estado": "sin_senal", "or_high": or_high, "or_low": or_low}


def operar_dia(dia: pd.DataFrame, fecha, saldo: float, cfg: Config):
    """Señal + filtros + tamaño + simulación. Devuelve (estado, operación o None, datos de la señal)."""
    s = senal(dia, fecha, cfg)
    if s["estado"] != "senal":
        return s["estado"], None, s
    j, d = s["i"], s["direccion"]
    if j + 1 >= len(dia):
        return "sin_vela_de_entrada", None, s
    entrada = dia.open.iloc[j + 1] + d * cfg.costes.ticks(dia.index[j + 1]) * cfg.tick
    stop = s["or_low"] if d == 1 else s["or_high"]
    r = (entrada - stop) * d
    if r <= 0:
        return "entrada_mas_alla_del_stop", None, s
    if cfg.tope_puntos is not None and r > cfg.tope_puntos:
        return "riesgo_mayor_que_tope", None, s
    if cfg.tope_pct is not None and r > cfg.tope_pct * entrada:
        return "riesgo_mayor_que_tope", None, s
    n = contratos(saldo, cfg.riesgo_pct, r, cfg.valor_punto)
    if n < 1:
        return "cero_contratos", None, s
    objetivo = entrada + d * cfg.objetivo_r * r
    op = ejecutar(dia, j, d, stop, objetivo, n, hora_local_a_utc(fecha, cfg.salida_tiempo, NUEVA_YORK),
                  cfg.tick, cfg.valor_punto, cfg.costes)
    if op is None:
        return "sin_vela_de_entrada", None, s
    op.riesgo_usd = r * cfg.valor_punto * n            # 1R = distancia al stop x contratos
    return "operada", op, s


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset(),
             desde=None, hasta=None):
    """Backtest día a día con saldo que se actualiza tras cada operación (el tamaño depende del saldo).
    Devuelve (operaciones, recuento de estados por día)."""
    ny = m1.index.tz_convert(NUEVA_YORK)
    rth = m1[(ny.hour * 60 + ny.minute >= 9 * 60 + 30) & (ny.hour < 16)]
    por_dia = dict(tuple(rth.groupby(rth.index.tz_convert(NUEVA_YORK).date)))
    fechas = sorted(por_dia)
    if desde is not None:
        fechas = [f for f in fechas if f >= pd.Timestamp(desde).date()]
    if hasta is not None:
        fechas = [f for f in fechas if f < pd.Timestamp(hasta).date()]
    saldo, ops, estados = cfg.saldo_inicial, [], {}
    for f in fechas:
        if f in excluir or pd.Timestamp(f).weekday() >= 5:
            continue
        dia = por_dia[f]
        estado, op, _ = operar_dia(dia, f, saldo, cfg)
        estados[estado] = estados.get(estado, 0) + 1
        if op is not None:
            op.saldo_antes = saldo
            ops.append(op)
            saldo += op.neto
    tabla = a_tabla(ops)
    return tabla, estados


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Señales (para la auditoría de look-ahead)."""
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion})
