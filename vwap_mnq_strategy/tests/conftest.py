import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import load_config  # noqa: E402


@pytest.fixture
def cfg():
    c = load_config()
    c["data"]["min_sessions"] = 1
    return c


def sesion_1m(fecha: str, precios: np.ndarray, volumen=None, inst: int = 1) -> pd.DataFrame:
    """Sesión RTH sintética de 1 min (09:30-16:00 NY, 390 velas) con OHLC = precio +/- 0,25."""
    assert len(precios) == 390
    idx = pd.date_range(f"{fecha} 09:30", periods=390, freq="1min", tz="America/New_York").tz_convert("UTC")
    p = np.asarray(precios, float)
    v = np.full(390, 100.0) if volumen is None else np.asarray(volumen, float)
    return pd.DataFrame({"open": p, "high": p + 0.25, "low": p - 0.25, "close": p, "volume": v, "instrument_id": inst},
                        index=idx)


@pytest.fixture
def hacer_sesion():
    return sesion_1m
