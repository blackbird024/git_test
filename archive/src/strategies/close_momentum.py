"""Estrategia 3: momentum de cierre en MNQ.

Idea (Gao, Han, Li y Zhou, 2018, "Market intraday momentum"): el rendimiento de la primera
media hora de la sesión ayuda a predecir el de la última media hora.

Reglas (fijadas ANTES de ver resultados):
  1. Rendimiento de la primera media hora = cierre de la vela de 9:59 - apertura de la de 9:30.
     (No usamos el cierre del día anterior: con el contrato continuo sin ajustar, el día del
     cambio de contrato habría un salto artificial.)
  2. Si es positivo -> compra; si es negativo -> venta. Si es exactamente 0, no se opera.
  3. Señal al cierre de la vela de 15:19 -> entrada en la apertura de las 15:20.
  4. Stop a `atr_mult` x ATR(14) del precio de referencia. Objetivo a `target_r` x stop.
  5. Si no toca ni stop ni objetivo, el motor cierra a las 15:50.
"""
from dataclasses import dataclass

import pandas as pd

from src.engine.types import LONG, SHORT, Signal
from src.indicators.basic import prior_atr


@dataclass
class CloseMomentum:
    atr_mult: float
    atr_by_date: dict
    instrument: str = "MNQ"
    target_r: float = 2.0
    signal_bar: str = "15:19"

    @property
    def name(self) -> str:
        return f"CM_atr{self.atr_mult:g}"

    @classmethod
    def build(cls, data: pd.DataFrame, atr_mult: float, **kw) -> "CloseMomentum":
        return cls(atr_mult, prior_atr(data), **kw)

    def signals_for_day(self, date, bars: dict[str, pd.DataFrame]) -> list[Signal]:
        df = bars.get(self.instrument)
        atr = self.atr_by_date.get(date)
        if df is None or atr is None or df.empty:
            return []
        tz = df.index.tz
        t930, t959 = pd.Timestamp(f"{date} 09:30", tz=tz), pd.Timestamp(f"{date} 09:59", tz=tz)
        t_sig = pd.Timestamp(f"{date} {self.signal_bar}", tz=tz)
        if t930 not in df.index or t959 not in df.index or t_sig not in df.index:
            return []
        first_half = df.at[t959, "close"] - df.at[t930, "open"]
        if first_half == 0:
            return []
        direction = LONG if first_half > 0 else SHORT
        ref = df.at[t_sig, "close"]
        stop = ref - direction * self.atr_mult * atr
        target = ref + direction * self.target_r * self.atr_mult * atr
        return [Signal(self.name, self.instrument, direction, t_sig, stop, target)]
