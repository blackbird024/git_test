import numpy as np
import pytest

from src import indicators as ind
from src.session_manager import build_bars


def test_vwap_ejemplo_a_mano():
    # tp = (h+l+c)/3: 10, 20, 30 ; volúmenes 1, 1, 2 -> VWAP acumulado 10, 15, 22.5
    h, l, c = np.array([11, 21, 31.0]), np.array([9, 19, 29.0]), np.array([10, 20, 30.0])
    v = np.array([1, 1, 2.0])
    np.testing.assert_allclose(ind.vwap(h, l, c, v, [0, 0, 0]), [10, 15, 22.5])


def test_vwap_se_reinicia_en_cada_sesion():
    h = l = c = np.array([10, 20, 100, 200.0])
    v = np.ones(4)
    np.testing.assert_allclose(ind.vwap(h, l, c, v, ["a", "a", "b", "b"]), [10, 15, 100, 150])


def test_vwap_volumen_cero_es_nan():
    h = l = c = np.array([10, 20.0])
    out = ind.vwap(h, l, c, np.array([0, 5.0]), [0, 0])
    assert np.isnan(out[0]) and out[1] == 20


def test_desviacion_bandas():
    h = l = c = np.array([10, 20.0])
    sd = ind.vwap_std(h, l, c, np.ones(2), [0, 0])
    np.testing.assert_allclose(sd, [0, 5])


def test_vwap_de_la_vela_15m_es_el_de_su_ultimo_minuto(cfg, hacer_sesion):
    precios = np.arange(390, dtype=float) + 100
    df = hacer_sesion("2024-03-11", precios)          # lunes tras el cambio de hora de EE. UU.
    ses = build_bars(df, cfg)
    b = ses.bars
    assert len(b) == 26 and b.session_valid.all()
    # vela 0: minutos 0..14, precios 100..114 con volumen igual -> VWAP = media = 107
    assert b.vwap_rth.iloc[0] == pytest.approx(107.0)
    assert b.start.iloc[0].tz_convert("America/New_York").strftime("%H:%M") == "09:30"


def test_sesion_incompleta_se_excluye(cfg, hacer_sesion):
    df = hacer_sesion("2024-03-12", np.full(390, 100.0))
    df = df.iloc[:210]                                 # cierre anticipado 13:00
    ses = build_bars(df, cfg)
    assert not ses.bars.session_valid.any()
