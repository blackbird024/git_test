"""El Monte Carlo vectorizado debe dar lo mismo que el simulador día a día."""
import numpy as np
import pandas as pd

from src.risk.apex_eod import simulate_evaluation
from src.validation.monte_carlo import simulate_paths, synthetic_days


def test_vectorized_matches_day_by_day(account):
    pnl, worst = synthetic_days(0.1, 400, n_paths=300, n_days=21, trades_per_day=2, seed=1)
    fast = simulate_paths(pnl, worst, account)
    idx = pd.bdate_range("2024-01-02", periods=21)
    outcomes = []
    for i in range(len(pnl)):
        daily = pd.DataFrame({"pnl": pnl[i], "min_intraday_pnl": worst[i]}, index=idx)
        outcomes.append(simulate_evaluation(daily, account, idx[0]).outcome)
    slow = pd.Series(outcomes).value_counts(normalize=True) * 100
    assert np.isclose(fast["% aprobadas"], round(slow.get("aprobada", 0), 1))
    assert np.isclose(fast["% suspendidas"], round(slow.get("suspendida", 0), 1))


def test_zero_edge_small_risk_mostly_expires(account):
    pnl, worst = synthetic_days(0.0, 150, n_paths=2000, n_days=21)
    res = simulate_paths(pnl, worst, account)
    assert res["% caducadas"] > 80
