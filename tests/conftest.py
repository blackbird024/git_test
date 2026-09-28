"""Utilidades para construir casos de prueba pequeños y calculables a mano."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import FirmAccount, Instrument, SystemRules  # noqa: E402

TZ = "America/New_York"


def make_bars(date: str, ohlc: list[tuple], start: str = "09:30") -> pd.DataFrame:
    """Velas de 1 minuto consecutivas a partir de `start` (hora de NY)."""
    idx = pd.date_range(f"{date} {start}", periods=len(ohlc), freq="1min", tz=TZ)
    df = pd.DataFrame(ohlc, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100
    return df


def ts(date: str, hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(f"{date} {hhmm}", tz=TZ)


class FixedSignals:
    """Estrategia falsa que devuelve señales fijas, para probar el motor aislado."""
    def __init__(self, signals, name="test"):
        self.signals = signals
        self.name = name

    def signals_for_day(self, date, bars):
        return [s for s in self.signals if s.time.date() == date]


@pytest.fixture
def instruments():
    return {
        "MNQ": Instrument("MNQ", tick=0.25, point_value=2.0, commission_rt=1.5,
                          slippage_ticks=1, group="indices_usa"),
        "MGC": Instrument("MGC", tick=0.1, point_value=10.0, commission_rt=1.5,
                          slippage_ticks=1, group="metales"),
    }


@pytest.fixture
def rules():
    return SystemRules(risk_per_trade=150, daily_budget=500, max_trades_per_day=3,
                       min_reward_risk=0.5, session_start="09:30", force_close="15:50",
                       entry_delay_bars=1)


@pytest.fixture
def account():
    return FirmAccount(start_balance=50_000, profit_target=3_000, max_drawdown=2_000,
                       daily_loss_limit=1_000, max_micros=60, access_days=30,
                       threshold_cap=None, dll_fails_account=False)
