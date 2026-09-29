"""Prueba de look-ahead: una estrategia honesta pasa la comprobación y una tramposa la suspende.
En el paso 1, cada estrategia real se somete a esta misma comprobación con datos reales."""
import numpy as np
import pandas as pd

from src.data.marcos import remuestrear, ultima_cerrada
from src.engine.lookahead import comprobar

IDX = pd.date_range("2024-01-15 14:00", periods=300, freq="1min", tz="UTC")
VELAS = pd.DataFrame({"close": 100 + np.cumsum(np.random.default_rng(1).normal(0, 1, 300))}, index=IDX)
VELAS["open"] = VELAS.close.shift(fill_value=100)
VELAS["high"] = VELAS[["open", "close"]].max(axis=1) + 0.1
VELAS["low"] = VELAS[["open", "close"]].min(axis=1) - 0.1
VELAS["volume"] = 1.0
CORTES = [IDX[100], IDX[200]]


def honesta(v):
    sube = v.close > v.close.rolling(10).mean()                 # solo velas pasadas y la actual (cerrada)
    s = v.index[sube & ~sube.shift(fill_value=False)]
    return pd.DataFrame({"t_senal": s})


def tramposa(v):
    sube = v.close.shift(-1) > v.close                           # ¡mira la vela siguiente!
    return pd.DataFrame({"t_senal": v.index[sube.fillna(False)]})


def test_honest_strategy_passes():
    assert comprobar(honesta, VELAS, CORTES) == []


def test_cheating_strategy_is_caught():
    assert comprobar(tramposa, VELAS, CORTES) != []


def test_higher_timeframe_only_after_close():
    h1 = remuestrear(VELAS, "1H")
    # A las 14:59:59 la vela de 14:00 aún no ha cerrado; a las 15:00 sí.
    assert ultima_cerrada(h1, pd.Timestamp("2024-01-15 14:59:59", tz="UTC")) is None
    assert ultima_cerrada(h1, pd.Timestamp("2024-01-15 15:00", tz="UTC")).name == IDX[0]
