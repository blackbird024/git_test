"""Estrategia 2: tendencia intradía con VWAP (MNQ y MGC).

VWAP = precio medio del día ponderado por volumen, acumulado desde las 9:30 ET.
Se calcula solo con velas ya cerradas, así que no mira el futuro.

Reglas (fijadas ANTES de ver resultados):
  1. Tendencia alcista: cierre > VWAP y cierre > apertura del día (9:30). Bajista: al revés.
  2. Entrada en retroceso: vela cuyo mínimo toca el VWAP (máximo, si es bajista) y que cierra
     de nuevo del lado de la tendencia.
  3. Solo señales entre 10:00 y 14:30 ET, y como máximo una por día.
  4. Stop: al otro lado del VWAP, a `atr_mult` x ATR(14). Objetivo: `target_r` x stop.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.engine.types import LONG, SHORT, Signal
from src.indicators.basic import prior_atr


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP acumulado de la sesión con precio típico (máximo + mínimo + cierre) / 3."""
    typical = (df.high + df.low + df.close) / 3
    vol = df.volume.astype(float)
    cum_vol = vol.cumsum().replace(0, np.nan)
    return (typical * vol).cumsum() / cum_vol


@dataclass
class VWAPTrend:
    instrument: str
    atr_mult: float
    atr_by_date: dict
    target_r: float = 2.0
    first_signal: str = "10:00"
    last_signal: str = "14:30"

    @property
    def name(self) -> str:
        return f"VWAP_{self.instrument}_atr{self.atr_mult:g}"

    @classmethod
    def build(cls, data: pd.DataFrame, instrument: str, atr_mult: float, **kw) -> "VWAPTrend":
        return cls(instrument, atr_mult, prior_atr(data), **kw)

    def signals_for_day(self, date, bars: dict[str, pd.DataFrame]) -> list[Signal]:
        df = bars.get(self.instrument)
        atr = self.atr_by_date.get(date)
        if df is None or atr is None or df.empty:
            return []
        tz = df.index.tz
        day = df[df.index >= pd.Timestamp(f"{date} 09:30", tz=tz)]
        if day.empty:
            return []
        vwap = session_vwap(day)
        day_open = day.open.iloc[0]
        window = (day.index >= pd.Timestamp(f"{date} {self.first_signal}", tz=tz)) & \
                 (day.index < pd.Timestamp(f"{date} {self.last_signal}", tz=tz))

        up = (day.close > vwap) & (day.close > day_open) & (day.low <= vwap)
        down = (day.close < vwap) & (day.close < day_open) & (day.high >= vwap)
        hits = day.index[window & (up | down)]
        if len(hits) == 0:
            return []
        t = hits[0]
        direction = LONG if up.loc[t] else SHORT
        ref, v = day.close.loc[t], vwap.loc[t]
        stop = v - direction * self.atr_mult * atr
        target = ref + direction * self.target_r * abs(ref - stop)
        return [Signal(self.name, self.instrument, direction, t, stop, target)]
