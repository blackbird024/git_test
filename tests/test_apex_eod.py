"""Pruebas del simulador de evaluación Apex EOD (cuenta 50K: objetivo 3.000, drawdown 2.000, DLL 1.000)."""
from dataclasses import replace

import pandas as pd

from src.risk.apex_eod import EXPIRED, FAILED, PASSED, simulate_evaluation


def daily(rows):
    """rows = [(pnl, peor_momento_intradia), ...] en días hábiles consecutivos."""
    idx = pd.bdate_range("2024-01-02", periods=len(rows))
    return pd.DataFrame(rows, columns=["pnl", "min_intraday_pnl"], index=idx)


def test_passes_when_target_reached(account):
    r = simulate_evaluation(daily([(1500, -100), (1600, -50)]), account, "2024-01-02")
    assert r.outcome == PASSED and r.trading_days == 2


def test_fails_touching_initial_threshold(account):
    r = simulate_evaluation(daily([(-900, -900), (-900, -900), (0, -200)]), account, "2024-01-02")
    # Saldo 48.200 tras dos días; umbral 48.000; peor momento del día 3 = 48.000 -> lo toca
    assert r.outcome == FAILED and r.reason == "umbral_eod"


def test_threshold_rises_only_at_close(account):
    # Día 1: gana 1.500 -> saldo 51.500 -> nuevo umbral 49.500 (y ya no baja).
    # Días 2 y 3: pierde 900 cada uno -> 50.600 -> 49.700 (nunca toca 49.500).
    # Día 4: peor momento -300 -> 49.400 <= 49.500 -> suspendida.
    rows = [(1500, 0), (-900, -900), (-900, -900), (0, -300)]
    r = simulate_evaluation(daily(rows), account, "2024-01-02")
    assert r.outcome == FAILED and r.end == pd.Timestamp("2024-01-05")


def test_unrealized_profit_does_not_raise_threshold(account):
    # Día con +2.500 no realizados que acaba en 0: el umbral NO sube (a diferencia del trailing intradía).
    r = simulate_evaluation(daily([(0, 0), (-1900, -1900)]), account, "2024-01-02")
    assert r.outcome != FAILED


def test_dll_stops_day_but_not_account(account):
    # Pierde 1.200 en el peor momento, pero el DLL de 1.000 corta la pérdida.
    r = simulate_evaluation(daily([(-1200, -1200)]), account, "2024-01-02")
    assert r.outcome == EXPIRED and r.final_balance == 49_000


def test_dll_fails_account_if_configured(account):
    strict = replace(account, dll_fails_account=True)
    r = simulate_evaluation(daily([(-1200, -1200)]), strict, "2024-01-02")
    assert r.outcome == FAILED and r.reason == "limite_diario"


def test_threshold_cap(account):
    # Gana 2.900 (saldo 52.900): sin tope el umbral sube a 50.900; con tope se queda en 50.100.
    # Luego pierde 900 tres días: 52.000 -> 51.100 -> 50.200.
    rows = [(2900, 0), (-900, -900), (-900, -900), (-900, -900)]
    capped = replace(account, threshold_cap=50_100)
    assert simulate_evaluation(daily(rows), capped, "2024-01-02").outcome == EXPIRED  # 50.200 > 50.100
    r = simulate_evaluation(daily(rows), account, "2024-01-02")
    assert r.outcome == FAILED and r.end == pd.Timestamp("2024-01-05")               # 50.200 <= 50.900


def test_expires_after_access_days(account):
    rows = [(10, 0)] * 40
    r = simulate_evaluation(daily(rows), account, "2024-01-02")
    assert r.outcome == EXPIRED
    assert r.end < pd.Timestamp("2024-01-02") + pd.Timedelta(days=30)
