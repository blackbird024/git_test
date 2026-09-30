"""Pruebas de estrés con las reglas congeladas: costes, deslizamiento, retraso de ejecución y sensibilidad (uno a uno).

- Zona de ruido con retraso: auditoria/src/variantes_zr.py (copia fiel con un único cambio; retraso 0 = original,
  probado en auditoria/tests). El retraso se aplica a TODAS las ejecuciones (entradas y salidas por chequeo).
- RSI(2) con retraso: `rsi2_retardo` es una copia de nq_rsi2.backtest_sesiones con un único cambio: el precio de entrada
  y de salida es la apertura del minuto `retardo` después de la reapertura de Globex (retraso 0 = original, probado).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from auditoria.src import variantes_zr
from src.strategies import nq_rsi2

from . import congeladas as K


def rsi2_retardo(m1: pd.DataFrame, excluir: frozenset, retardo: int, cfg: nq_rsi2.Config = K.RSI2_SURVIVOR_V1) -> pd.DataFrame:
    s = nq_rsi2.preparar(m1, cfg)
    t_ns = m1.index.asi8
    objetivo = pd.DatetimeIndex(s.t_primera).asi8 + retardo * 60_000_000_000
    k = np.searchsorted(t_ns, objetivo, side="left").clip(0, len(m1) - 1)
    precio = m1.open.to_numpy()[k]
    t_ej = m1.index[k]
    factor = (s.close_aj / s.close).to_numpy()            # ajuste de la sesión (constante dentro de la sesión)
    n, ops, i = len(s), [], 0
    c, pv = cfg.costes, cfg.valor_punto * cfg.contratos
    while i < n - 1:
        if not s.senal.iloc[i] or s.index[i + 1].date() in excluir:
            i += 1
            continue
        e = i + 1
        k_ = e
        motivo = None
        while k_ < n:
            if k_ == n - 1:
                break
            if s.rsi.iloc[k_] > cfg.salida or k_ - e + 1 >= cfg.max_dias:
                motivo = "rsi" if s.rsi.iloc[k_] > cfg.salida else "tiempo"
                break
            k_ += 1
        x = k_ + 1 if k_ + 1 < n else k_
        ret_bruto = (precio[x] * factor[x]) / (precio[e] * factor[e]) - 1
        desl = (c.ticks(t_ej[e]) + c.ticks(t_ej[x])) * cfg.tick
        neto = (precio[e] * ret_bruto - desl) * pv - c.comision(cfg.contratos)
        ret_neto = neto / (precio[e] * pv)
        ops.append({"t_senal": s.t_ultima.iloc[i], "t_entrada": t_ej[e], "t_salida": t_ej[x], "sesiones": max(x - e, 1),
                    "ret_%": ret_neto * 100, "neto": neto,
                    "r": ret_neto / s.vol20.iloc[i] if s.vol20.iloc[i] > 0 else np.nan, "motivo": motivo or "fin_de_datos"})
        i = x
    return K.utc(pd.DataFrame(ops))


def zr_retardo(m1, excluir, retardo: int, cfg=K.NOISE_ZONE_SURVIVOR_V1) -> pd.DataFrame:
    return K.utc(variantes_zr.backtest(m1, cfg, excluir, retardo))


def sensibilidad_rsi2() -> dict:
    b = K.RSI2_SURVIVOR_V1
    out = {f"entrada={v}": b.con(entrada=float(v)) for v in (18, 19, 21, 22)}
    out.update({f"salida={v}": b.con(salida=float(v)) for v in (65, 75)})
    out.update({f"max_dias={v}": b.con(max_dias=v) for v in (4, 6)})
    out.update({f"sma={v}": b.con(sma=v) for v in (180, 220)})
    return out


def sensibilidad_zr() -> dict:
    b = K.NOISE_ZONE_SURVIVOR_V1
    out = {f"dias_ruido={v}": b.con(dias_ruido=v) for v in (13, 15)}
    out.update({f"mult={v}": b.con(mult=v) for v in (0.9, 1.1)})
    return out
