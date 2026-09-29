import numpy as np
import pandas as pd

from src.strategy import entry_signals, model_conditions


def _x(close, vwap, open_=None, low=None, high=None, e20=None, e50=None, e200=None, ses=None):
    n = len(close)
    c = np.asarray(close, float)
    return pd.DataFrame({"close": c, "open": c if open_ is None else open_, "low": c - 1 if low is None else low,
                         "high": c + 1 if high is None else high, "vwap": vwap, "ema_fast": e20 if e20 is not None else [0] * n,
                         "ema_medium": e50 if e50 is not None else [0] * n, "ema_slow": e200 if e200 is not None else [0] * n,
                         "ema_slow_slope": [1] * n, "vwap_slope": [1] * n, "session": ses or ["d"] * n})


def test_modelos():
    x = _x([11, 11, 11, 9], [10] * 4, e20=[12, 10, 10, 10], e50=[5, 5, 20, 5], e200=[10, 10, 10, 10])
    assert list(model_conditions(x, "A")[0]) == [True, True, True, False]
    assert list(model_conditions(x, "C")[0]) == [False, False, True, False]   # EMA50 > EMA200 solo en la 3.ª... y cierre > EMA200
    assert list(model_conditions(x, "D")[0]) == [False, False, True, False]


def test_breakout_exige_cruce_y_vela_confirmada():
    p = {"model": "A", "trend_filters": [], "entry_type": "breakout"}
    x = _x([9, 11, 12, 9], [10] * 4, open_=[9, 10, 12.5, 10])
    np.testing.assert_array_equal(entry_signals(x, p), [0, 1, 0, -1])


def test_pullback():
    p = {"model": "A", "trend_filters": [], "entry_type": "pullback"}
    # vela 1: venía por encima, el mínimo toca el VWAP (10) y cierra alcista por encima -> largo
    x = _x([12, 12, 12], [10] * 3, open_=[12, 11, 12.5], low=[11.5, 10, 11.8], e20=[11, 11, 11])
    np.testing.assert_array_equal(entry_signals(x, p), [0, 1, 0])


def test_state_y_filtro_de_tendencia():
    p = {"model": "A", "trend_filters": ["vwap_slope"], "entry_type": "state"}
    x = _x([11, 9], [10, 10])
    x["vwap_slope"] = [-1, -1]
    np.testing.assert_array_equal(entry_signals(x, p), [0, -1])
