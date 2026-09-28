"""Estrategia 1: Opening Range Breakout (ruptura del rango de apertura) en MNQ.

Reglas (fijadas ANTES de ver resultados, sin optimizar):
  1. Rango de apertura = máximo y mínimo de los primeros `or_minutes` minutos desde las 9:30 ET.
  2. La primera vela de 1 minuto que CIERRA por encima del máximo -> señal de compra;
     por debajo del mínimo -> señal de venta. Solo la primera ruptura del día.
  3. Solo se buscan rupturas hasta `last_signal` (12:00 ET).
  4. Stop:
       "range": en el lado opuesto del rango de apertura.
       "atr":   a `atr_mult` x ATR(14) del precio de la señal.
  5. Objetivo: `target_r` veces la distancia al stop (1,5R).
  6. Si no se toca ni stop ni objetivo, el motor cierra a las 15:50.
"""
from dataclasses import dataclass

import pandas as pd

from src.engine.types import LONG, SHORT, Signal
from src.indicators.basic import prior_atr


@dataclass
class ORB:
    or_minutes: int
    stop_mode: str                  # "range" o "atr"
    atr_by_date: dict               # ATR conocido al empezar cada día (ver prior_atr)
    instrument: str = "MNQ"
    target_r: float = 1.5
    atr_mult: float = 0.25
    last_signal: str = "12:00"

    @property
    def name(self) -> str:
        return f"ORB{self.or_minutes}_{self.stop_mode}"

    @classmethod
    def build(cls, data: pd.DataFrame, or_minutes: int, stop_mode: str, **kw) -> "ORB":
        return cls(or_minutes, stop_mode, prior_atr(data), **kw)

    def signals_for_day(self, date, bars: dict[str, pd.DataFrame]) -> list[Signal]:
        df = bars.get(self.instrument)
        atr = self.atr_by_date.get(date)
        if df is None or atr is None or df.empty:
            return []
        open_ts = df.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
        or_end = open_ts + pd.Timedelta(minutes=self.or_minutes)
        opening = df[(df.index >= open_ts) & (df.index < or_end)]
        # Exigimos el rango completo: si faltan velas, ese día no se opera.
        if len(opening) < self.or_minutes:
            return []
        hi, lo = opening.high.max(), opening.low.min()

        last = pd.Timestamp(f"{date} {self.last_signal}", tz=df.index.tz)
        after = df[(df.index >= or_end) & (df.index < last)]
        breaks = after[(after.close > hi) | (after.close < lo)]
        if breaks.empty:
            return []
        bar = breaks.iloc[0]
        direction = LONG if bar.close > hi else SHORT
        ref = bar.close  # precio de referencia; la entrada real será en la vela siguiente

        if self.stop_mode == "range":
            stop = lo if direction == LONG else hi
        else:
            stop = ref - direction * self.atr_mult * atr
        risk = abs(ref - stop)
        target = ref + direction * self.target_r * risk
        return [Signal(self.name, self.instrument, direction, breaks.index[0], stop, target)]
