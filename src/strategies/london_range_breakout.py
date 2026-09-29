"""London Range Breakout en el oro (reglas en edges/london_range_breakout_gold.md).

Todo con velas de 1 minuto (sin remuestrear). Horas de las reglas en Europe/London, convertidas a UTC día a día:
  - rango: velas que empiezan entre las 08:00 y las 08:59 de Londres (fijo desde las 09:00);
  - señal: primera vela que empieza entre las 09:00 y las 16:28 y CIERRA estrictamente fuera del rango;
  - entrada en la apertura de la vela siguiente (motor estándar), stop en el otro extremo del rango,
    objetivo 2R, salida por tiempo a las 16:30 de Londres; como mucho 1 operación al día.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.engine.costes import Costes
from src.engine.ejecucion import a_tabla, ejecutar
from src.horas import LONDRES, hora_local_a_utc

MOTIVOS = ("operada", "rango_incompleto", "sin_ruptura", "sin_vela_de_entrada")


@dataclass(frozen=True)
class Config:
    # --- parámetros (fijos en esta fase) ---
    rango: tuple = ("08:00", "09:00")        # hora de Londres
    objetivo_r: float = 2.0
    cierre: str = "16:30"                    # hora de Londres
    # --- fijos ---
    ultima_senal: str = "16:29"              # la vela de señal debe empezar antes de esta hora
    min_velas_rango: int = 50
    contratos: int = 1
    tick: float = 0.10
    valor_punto: float = 10.0                # MGC
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def dias_londres(m1: pd.DataFrame) -> dict:
    """Velas de 1M agrupadas por fecha de Londres (solo de 07:00 a 17:00 de Londres, lo que se usa)."""
    local = m1.index.tz_convert(LONDRES)
    uso = m1[(local.hour >= 7) & (local.hour < 17)]
    return dict(tuple(uso.groupby(uso.index.tz_convert(LONDRES).date)))


def operar_dia(fecha, dia: pd.DataFrame, cfg: Config):
    """Devuelve (motivo, operación o None)."""
    t = lambda hhmm: hora_local_a_utc(fecha, hhmm, LONDRES)  # noqa: E731
    idx = dia.index
    rango = dia[(idx >= t(cfg.rango[0])) & (idx < t(cfg.rango[1]))]
    if len(rango) < cfg.min_velas_rango:
        return "rango_incompleto", None
    alto, bajo = rango.high.max(), rango.low.min()
    ventana = np.flatnonzero((idx >= t(cfg.rango[1])) & (idx < t(cfg.ultima_senal)))
    C = dia.close.to_numpy()
    for j in ventana:
        if C[j] > alto or C[j] < bajo:
            d = 1 if C[j] > alto else -1
            if j + 1 >= len(dia):
                return "sin_vela_de_entrada", None
            entrada = dia.open.iloc[j + 1] + d * cfg.costes.ticks(idx[j + 1]) * cfg.tick
            stop = bajo if d == 1 else alto
            r = (entrada - stop) * d
            if r <= 0:                                   # abre ya al otro lado del stop: no se puede entrar
                return "sin_vela_de_entrada", None
            op = ejecutar(dia, j, d, stop, entrada + d * cfg.objetivo_r * r, cfg.contratos, t(cfg.cierre),
                          cfg.tick, cfg.valor_punto, cfg.costes)
            if op is None:
                return "sin_vela_de_entrada", None
            op.riesgo_usd = r * cfg.valor_punto * cfg.contratos      # 1R = distancia al stop (sin comisión)
            return "operada", op
        # la ruptura debe ser por cierre: una mecha fuera del rango no cuenta
    return "sin_ruptura", None


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()):
    """(operaciones, recuento de días por motivo)."""
    ops, motivos = [], {m: 0 for m in MOTIVOS}
    for fecha, dia in dias_londres(m1).items():
        if fecha in excluir or pd.Timestamp(fecha).weekday() >= 5:
            continue
        motivo, op = operar_dia(fecha, dia, cfg)
        motivos[motivo] += 1
        if op is not None:
            ops.append(op)
    tabla = a_tabla(ops)
    if len(tabla):
        tabla["rango_usd"] = (tabla.stop - tabla.entrada).abs()   # distancia al stop en $ de precio
    return tabla, motivos


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": ops.t_senal, "direccion": ops.direccion})
