"""BOT 01 (RSI(2) NQ) y BOT 02 (zona de ruido NQ): envoltorios SIN CAMBIOS sobre el código original
(src/strategies/nq_rsi2.py y src/strategies/zona_ruido.py), para compararlas y combinarlas con las nuevas.
Costes: los de su propio código (zona de ruido: 1 $/lado y 1 tick; RSI(2): Costes() del proyecto)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.strategies import base as B
from src.engine.costes import Costes
from src.strategies import nq_rsi2, zona_ruido as z


def zona_ruido(ctx, mult: float = 1.0) -> pd.DataFrame:
    def f():
        cfg = z.Config().con(ticks_entrada=int(round(mult)), ticks_salida=int(round(mult)), comision_lado=1.0 * mult)
        o, _ = z.backtest(ctx.m1, cfg, ctx.excluir)
        o = o.copy()
        o["t_entrada"] = pd.to_datetime(o.t_entrada).dt.tz_convert("UTC")
        o["t_salida"] = pd.to_datetime(o.t_salida).dt.tz_convert("UTC")
        o["r"] = np.nan
        return o
    return B.cache(ctx, ("zr", mult), f)


def rsi2(ctx, mult: float = 1.0) -> pd.DataFrame:
    def f():
        o = nq_rsi2.backtest(ctx.m1, nq_rsi2.Config().con(costes=Costes(multiplicador=mult)), ctx.excluir).copy()
        o["t_entrada"] = pd.to_datetime(o.t_entrada, utc=True)
        o["t_salida"] = pd.to_datetime(o.t_salida, utc=True)
        o["bruto"] = o.neto + Costes(multiplicador=mult).comision(1)    # aproximado: solo para mostrar costes
        o["direccion"] = 1
        return o
    return B.cache(ctx, ("rsi2", mult), f)
