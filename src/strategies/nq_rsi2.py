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
    # --- parámetros libres (máximo 3; la entrada = 20 la fija la especificación) ---
    entrada: float = 20.0
    salida: float = 70.0
    max_dias: int = 5
    filtro_vol: float | None = None    # paso 2: no entrar si ATR(5) / ATR(50) > este valor
    stop_atr: float | None = None      # paso 2: stop de catástrofe a k x ATR(14) desde la entrada
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
    # Rango verdadero en la serie ajustada (sin saltos de roll), en % del precio.
    h_aj, l_aj = s.high * s.close_aj / s.close, s.low * s.close_aj / s.close
    tr = pd.concat([h_aj - l_aj, (h_aj - s.close_aj.shift()).abs(), (l_aj - s.close_aj.shift()).abs()], axis=1).max(axis=1)
    s["atr14_pct"] = (tr / s.close_aj).rolling(14).mean()
    s["ratio_vol"] = tr.rolling(5).mean() / tr.rolling(50).mean()
    s["senal"] = (s.close_aj > s.sma) & (s.rsi < cfg.entrada)
    if cfg.filtro_vol is not None:
        s["senal"] &= s.ratio_vol <= cfg.filtro_vol
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
        precio_e = s.open.iloc[e]
        # Stop de catástrofe (en la serie ajustada, para que un cambio de contrato no lo mueva).
        stop_aj = None
        if cfg.stop_atr is not None:
            stop_aj = s.open_aj.iloc[e] * (1 - cfg.stop_atr * s.atr14_pct.iloc[i])
        k, motivo, ret_bruto = e, None, None
        while k < n:
            low_aj = s.low.iloc[k] * s.close_aj.iloc[k] / s.close.iloc[k]
            if stop_aj is not None and low_aj <= stop_aj:      # salta el stop durante la sesión k
                ab_aj = s.open_aj.iloc[k] if k > e else s.open_aj.iloc[e]
                ret_bruto = min(stop_aj, ab_aj) / s.open_aj.iloc[e] - 1
                motivo, x, t_x = "stop", k, s.t_primera.iloc[k]
                break
            if k == n - 1:
                break
            if s.rsi.iloc[k] > cfg.salida or k - e + 1 >= cfg.max_dias:
                motivo = "rsi" if s.rsi.iloc[k] > cfg.salida else "tiempo"
                break
            k += 1
        if motivo != "stop":
            x = k + 1 if k + 1 < n else k                      # salida en la apertura siguiente
            ret_bruto = s.open_aj.iloc[x] / s.open_aj.iloc[e] - 1
            t_x = s.t_primera.iloc[x]
            motivo = motivo or "fin_de_datos"
        desl = (c.ticks(s.t_primera.iloc[e]) + c.ticks(t_x)) * cfg.tick
        neto = (precio_e * ret_bruto - desl) * pv - c.comision(cfg.contratos)
        ret_neto = neto / (precio_e * pv)
        ops.append({"t_senal": s.t_ultima.iloc[i], "t_entrada": s.t_primera.iloc[e], "t_salida": t_x,
                    "sesiones": max(x - e, 1), "ret_%": ret_neto * 100, "neto": neto,
                    "r": ret_neto / s.vol20.iloc[i] if s.vol20.iloc[i] > 0 else np.nan, "motivo": motivo})
        i = x                                                  # nueva señal posible desde el cierre de la sesión de salida
    return pd.DataFrame(ops)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    s = preparar(m1, cfg)
    return pd.DataFrame({"t_senal": s.t_ultima[s.senal].to_numpy()})


def rendimiento_diario_medio(m1: pd.DataFrame) -> float:
    """Rendimiento medio por sesión de estar siempre comprado (referencia de comprar y mantener)."""
    return sesiones(m1).ret.iloc[1:].mean()
