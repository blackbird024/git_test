import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common import load_config, params  # noqa: E402


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def inst(cfg):
    return dict(cfg["instruments"]["MNQ"])


def sesion(fecha, precios, vol=None):
    """Sesión 09:30-16:00 NY de 1 min con OHLC = precio +/- 0,25."""
    idx = pd.date_range(f"{fecha} 09:30", periods=390, freq="1min", tz="America/New_York").tz_convert("UTC")
    p = np.asarray(precios, float)
    return pd.DataFrame({"open": p, "high": p + 0.25, "low": p - 0.25, "close": p,
                         "volume": np.full(390, 100.0) if vol is None else np.asarray(vol, float), "instrument_id": 1}, index=idx)


@pytest.fixture
def hacer():
    return sesion


@pytest.fixture
def p(cfg):
    return params(cfg)
