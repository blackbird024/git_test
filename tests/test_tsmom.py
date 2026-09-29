"""Pruebas del seguimiento de tendencia (series inventadas)."""
import numpy as np
import pandas as pd

from src.strategies.tsmom import portfolio, stats, weights


def test_uptrend_goes_long_and_no_lookahead():
    idx = pd.bdate_range("2015-01-01", periods=600)
    rets = pd.DataFrame({"A": np.full(600, 0.001) + np.tile([0.004, -0.004], 300)}, index=idx)
    w = weights(rets)
    assert (w.A.iloc[300:] > 0).all()                      # tendencia alcista -> largo
    # La posición cambia solo al día siguiente de un fin de mes.
    changes = w.A.diff().abs() > 1e-12
    prev_is_month_end = idx.to_series().shift(1).dt.is_month_end | (
        idx.to_series().shift(1).dt.month != idx.to_series().dt.month)
    assert (prev_is_month_end[changes.to_numpy()]).all()


def test_costs_reduce_returns_and_stats_keys():
    idx = pd.bdate_range("2015-01-01", periods=600)
    rets = pd.DataFrame({"A": np.full(600, 0.001) + np.tile([0.004, -0.004], 300)}, index=idx)
    rolls = pd.DataFrame({"A": False}, index=idx)
    pf = portfolio(rets, rolls, weights(rets), cost_bps=2)
    assert (pf.neto <= pf.bruto + 1e-15).all() and pf.coste.sum() > 0
    assert {"sharpe", "t", "pf_mensual"} <= set(stats(pf.neto))
