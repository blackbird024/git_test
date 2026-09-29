import numpy as np
import pandas as pd

from src.backtester import run
from src.data_loader import build
from src.strategy import entry_signals, features

from .conftest import sesion


def _datos(n=30, seed=0):
    rng = np.random.default_rng(seed)
    partes, nivel = [], 100.0
    for d in pd.bdate_range("2024-01-02", periods=n):
        pr = nivel + np.cumsum(rng.normal(0, 0.5, 390))
        nivel = pr[-1]
        partes.append(sesion(str(d.date()), np.round(pr * 4) / 4, rng.integers(50, 500, 390)))
    return pd.concat(partes)


def test_futuro_no_cambia_el_pasado(cfg, inst, p):
    df = _datos()
    corte = df.index[len(df) // 2]
    alt = df.copy()
    m = alt.index >= corte
    alt.loc[m, ["open", "high", "low", "close"]] *= 1.3
    alt.loc[m, "volume"] *= 5
    pp = dict(p, model="D", entry_type="pullback", trend_filters=["ema200_slope", "vwap_slope"])
    a = features(build(df, inst, cfg["general"]).bars, pp)
    b = features(build(alt, inst, cfg["general"]).bars, pp)
    antes = ((a.start + pd.Timedelta(minutes=15)) <= corte).to_numpy()
    for col in ["vwap", "ema_fast", "ema_medium", "ema_slow", "atr", "vwap_slope", "struct_low"]:
        np.testing.assert_allclose(a[col].to_numpy()[antes], b[col].to_numpy()[antes], equal_nan=True)
    np.testing.assert_array_equal(entry_signals(a, pp)[antes], entry_signals(b, pp)[antes])


def test_operaciones_previas_no_cambian(cfg, inst, p):
    df = _datos()
    corte = pd.Timestamp(df.index[len(df) // 2]).normalize() + pd.Timedelta(hours=4)
    pp = dict(p, model="B")
    sa, sb = build(df, inst, cfg["general"]), build(df[df.index < corte], inst, cfg["general"])
    ta = run(features(sa.bars, pp), sa.sub, pp, inst, 50_000).trades
    tb = run(features(sb.bars, pp), sb.sub, pp, inst, 50_000).trades
    ta = ta[pd.to_datetime(ta.exit_time) < corte.tz_localize(None)].reset_index(drop=True)
    assert len(ta) > 0
    pd.testing.assert_frame_equal(ta, tb.reset_index(drop=True))
