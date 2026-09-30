"""Pruebas del Survivor Analysis: integridad de las versiones congeladas, reproducción exacta, copias fieles (retraso 0 =
original), mark-to-market que suma el neto, rasgos sin información futura y herramientas del forward."""
import numpy as np
import pandas as pd
import pytest

from bot_lab.core.datos import Contexto
from src.data.datos import excluidos, velas_1m
from src.strategies import nq_rsi2
from survivor.src import caracteristicas as CA
from survivor.src import cartera as CT
from survivor.src import congeladas as K
from survivor.src import estres as ES


@pytest.fixture(scope="module")
def datos():
    m = velas_1m("NQ")
    m = m[(m.index >= "2017-01-01") & (m.index < "2020-01-01")]
    return m, excluidos("NQ")


def test_integridad_del_codigo_original():
    assert all(K.comprobar_integridad().values())


def test_parametros_congelados():
    assert (K.RSI2_SURVIVOR_V1.entrada, K.RSI2_SURVIVOR_V1.salida, K.RSI2_SURVIVOR_V1.max_dias, K.RSI2_SURVIVOR_V1.sma) == (20, 70, 5, 200)
    assert (K.NOISE_ZONE_SURVIVOR_V1.dias_ruido, K.NOISE_ZONE_SURVIVOR_V1.mult, K.NOISE_ZONE_SURVIVOR_V1.cada) == (14, 1.0, 30)


def test_reproduce_la_auditoria_operacion_a_operacion():
    m, ex = velas_1m("NQ"), excluidos("NQ")
    a = pd.read_csv(K.AUDITORIA / "operaciones_rsi2.csv")
    r = K.rsi2(m, ex)
    assert len(r) == len(a) and np.allclose(r.neto, a.neto)


def test_rsi2_con_retraso_0_es_el_original(datos):
    m, ex = datos
    a, b = K.rsi2(m, ex), ES.rsi2_retardo(m, ex, 0)
    assert len(a) == len(b) and np.allclose(a.neto, b.neto) and (a.t_entrada.values == b.t_entrada.values).all()


def test_costes_multiplicador_1_es_el_original(datos):
    m, ex = datos
    a, b = K.zona_ruido(m, ex), K.zona_ruido(m, ex, K.cfg_zr_costes(1.0))
    assert np.allclose(a.neto, b.neto)
    c = K.zona_ruido(m, ex, K.cfg_zr_costes(1.0, 1))
    assert np.allclose(a.neto - c.neto, 1.0)             # +1 tick por lado = 0,25 × 2 lados × 2 $ = 1 $


def test_mark_to_market_suma_el_neto(datos):
    m, ex = datos
    r = K.rsi2(m, ex)
    s = nq_rsi2.preparar(m, K.RSI2_SURVIVOR_V1)
    assert CT.rsi2_mtm(r, s, None).sum() == pytest.approx(r.neto.sum())


def test_rasgos_de_la_zona_de_ruido_no_usan_el_futuro(datos):
    m, ex = datos
    z = K.zona_ruido(m, ex)
    o = z[pd.DatetimeIndex(z.t_entrada) < pd.Timestamp("2019-06-01", tz="UTC")].tail(20).reset_index(drop=True)
    completo = CA.zona_ruido(Contexto(m, ex), o, CA.tabla_diaria(Contexto(m, ex)))
    corte = o.t_entrada.max()                              # datos solo hasta la última entrada (excluida)
    c2 = Contexto(m[m.index < corte], ex)
    parcial = CA.zona_ruido(c2, o, CA.tabla_diaria(c2))
    cols = ["VOL_ATR", "TENDENCIA", "dist_vwap_atr", "hueco_atr", "noche_ret_atr", "rango_previo_atr"]
    pd.testing.assert_frame_equal(completo[cols], parcial[cols])
