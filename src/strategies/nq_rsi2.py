"""Ventaja 3 — Nasdaq: RSI(2) de Connors con filtro de la media de 200 (reglas en edges/nq_rsi2.md).

Velas diarias = sesiones de CME construidas desde 1M. Los indicadores se calculan sobre cierres ajustados
por los cambios de contrato. La señal se decide al CIERRE de la sesión y se ejecuta en la APERTURA de la
siguiente (reapertura de Globex, 18:00 de Nueva York: apertura de sesión -> 2 ticks de deslizamiento).
El resultado de cada operación se calcula con la serie ajustada (así un cambio de contrato durante la
operación no crea ganancias o pérdidas falsas).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.data.datos import sesiones
from src.engine.costes import Costes


@dataclass(frozen=True)
class Config:
    # --- parámetros libres (3) ---
    entrada: float = 20.0
    salida: float = 70.0
    max_dias: int = 5
    # --- fijos ---
    sma: int = 200
    rsi_n: int = 2
    tick: float = 0.25
    valor_punto: float = 2.0          # MNQ
    contratos: int = 1
    costes: Costes = Costes()

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def rsi(close: pd.Series, n: int) -> pd.Series:
    """RSI de Wilder."""
    delta = close.diff()
    sube = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    baja = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    valor = 100 - 100 / (1 + sube / baja.where(baja > 0))
    return valor.where(baja > 0, 100.0).where(delta.notna().cumsum() > 0)   # sin bajadas = 100


def preparar(m1: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    s = sesiones(m1)
    s["rsi"] = rsi(s.close_aj, cfg.rsi_n)
    s["sma"] = s.close_aj.rolling(cfg.sma).mean()
    s["vol20"] = s.ret.rolling(20, min_periods=10).std()
    s["senal"] = (s.close_aj > s.sma) & (s.rsi < cfg.entrada)
    return s


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()) -> pd.DataFrame:
    s = preparar(m1, cfg)
    n, ops, i = len(s), [], 0
    c, pv = cfg.costes, cfg.valor_punto * cfg.contratos
    while i < n - 1:
        if not s.senal.iloc[i] or s.index[i + 1].date() in excluir:
            i += 1
            continue
        e = i + 1                                              # entrada en la apertura de la sesión siguiente
        k = e
        while k < n - 1:
            dias = k - e + 1
            if s.rsi.iloc[k] > cfg.salida or dias >= cfg.max_dias:
                break
            k += 1
        x = k + 1 if k + 1 < n else k                          # salida en la apertura siguiente
        precio_e = s.open.iloc[e]
        ret_bruto = s.open_aj.iloc[x] / s.open_aj.iloc[e] - 1
        desl = (c.ticks(s.t_primera.iloc[e]) + c.ticks(s.t_primera.iloc[x])) * cfg.tick
        neto = (precio_e * ret_bruto - desl) * pv - c.comision(cfg.contratos)
        ret_neto = neto / (precio_e * pv)
        ops.append({"t_senal": s.t_ultima.iloc[i], "t_entrada": s.t_primera.iloc[e], "t_salida": s.t_primera.iloc[x],
                    "sesiones": x - e, "ret_%": ret_neto * 100, "neto": neto,
                    "r": ret_neto / s.vol20.iloc[i] if s.vol20.iloc[i] > 0 else np.nan,
                    "motivo": "rsi" if s.rsi.iloc[k] > cfg.salida else "tiempo"})
        i = x                                                  # nueva señal posible desde el cierre de la sesión de salida
    return pd.DataFrame(ops)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    s = preparar(m1, cfg)
    return pd.DataFrame({"t_senal": s.t_ultima[s.senal].to_numpy()})


def rendimiento_diario_medio(m1: pd.DataFrame) -> float:
    """Rendimiento medio por sesión de estar siempre comprado (referencia de comprar y mantener)."""
    return sesiones(m1).ret.iloc[1:].mean()
