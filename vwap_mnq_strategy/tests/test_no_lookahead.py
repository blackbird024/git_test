"""Cambiar los datos POSTERIORES a un instante no puede cambiar nada calculado antes de ese instante."""
import numpy as np
import pandas as pd

from src.backtester import run
from src.session_manager import build_bars
from src.signals import añadir_indicadores, señales

rng = np.random.default_rng(0)


def _datos(hacer_sesion, n_dias=30):
    dias = pd.bdate_range("2024-01-02", periods=n_dias)
    partes = []
    nivel = 100.0
    for d in dias:
        p = nivel + np.cumsum(rng.normal(0, 0.5, 390))
        nivel = p[-1]
        partes.append(hacer_sesion(str(d.date()), np.round(p * 4) / 4, rng.integers(50, 500, 390)))
    return pd.concat(partes)


def _preparar(df, cfg):
    cfg = dict(cfg)
    cfg["_vwap_col"] = "vwap_rth"
    ses = build_bars(df, cfg)
    return ses, añadir_indicadores(ses.bars, cfg)


def test_indicadores_y_senales_no_miran_el_futuro(cfg, hacer_sesion):
    df = _datos(hacer_sesion)
    corte = df.index[len(df) // 2]
    alterado = df.copy()
    m = alterado.index >= corte
    alterado.loc[m, ["open", "high", "low", "close"]] *= 1.5
    alterado.loc[m, "volume"] *= 3
    _, a = _preparar(df, cfg)
    _, b = _preparar(alterado, cfg)
    antes = (a.start + pd.Timedelta(minutes=15)) <= corte          # velas cerradas antes del corte
    for col in ["vwap", "atr", "ema", "rsi", "vwap_slope", "close"]:
        pd.testing.assert_series_equal(a.loc[antes, col], b.loc[antes, col], check_names=False)
    sa, sb = señales(a, "vwap", "cross"), señales(b, "vwap", "cross")
    np.testing.assert_array_equal(sa[antes.to_numpy()], sb[antes.to_numpy()])


def test_operaciones_cerradas_antes_del_corte_no_cambian(cfg, hacer_sesion):
    df = _datos(hacer_sesion)
    corte = pd.Timestamp(df.index[len(df) // 2]).normalize() + pd.Timedelta(hours=4)   # entre sesiones
    ses_a, a = _preparar(df, cfg)
    ses_b, b = _preparar(df[df.index < corte], cfg)
    ta = run(a, ses_a.sub, cfg).trades
    tb = run(b, ses_b.sub, cfg).trades
    ta = ta[pd.to_datetime(ta.exit_time) < corte.tz_localize(None)].reset_index(drop=True)
    assert len(ta) > 0
    pd.testing.assert_frame_equal(ta, tb.reset_index(drop=True))
