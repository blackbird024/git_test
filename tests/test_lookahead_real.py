"""Look-ahead con DATOS REALES: las señales anteriores a un corte no pueden cambiar al añadir datos
posteriores. Se corta en sábado (sin mercado) para no partir una sesión. Se salta si no hay datos."""
import pandas as pd
import pytest

from src.data.datos import PROCESADOS, velas_1m
from src.engine.lookahead import comprobar
from src.strategies import barrido_londres, nq_rsi2

hay_datos = pytest.mark.skipif(not (PROCESADOS / "GC_1M.parquet").exists(), reason="sin datos procesados")
SABADOS = [pd.Timestamp("2019-03-09", tz="UTC"), pd.Timestamp("2019-04-13", tz="UTC")]
SABADOS_LARGO = [pd.Timestamp("2018-11-10", tz="UTC"), pd.Timestamp("2019-03-09", tz="UTC")]


@hay_datos
def test_london_sweep_no_lookahead():
    m1 = velas_1m("GC")
    tramo = m1[(m1.index >= "2019-02-01") & (m1.index < "2019-05-01")]
    assert comprobar(barrido_londres.senales, tramo, SABADOS) == []


@hay_datos
def test_rsi2_no_lookahead():
    m1 = velas_1m("NQ")
    tramo = m1[(m1.index >= "2018-01-01") & (m1.index < "2019-06-01")]
    assert comprobar(nq_rsi2.senales, tramo, SABADOS) == []


@hay_datos
def test_london_range_breakout_no_lookahead():
    from src.strategies import london_range_breakout
    m1 = velas_1m("GC")
    tramo = m1[(m1.index >= "2019-02-01") & (m1.index < "2019-05-01")]
    assert len(london_range_breakout.senales(tramo)) > 10          # la prueba no pasa "en vacío"
    assert comprobar(london_range_breakout.senales, tramo, SABADOS) == []


@hay_datos
def test_smc_no_lookahead():
    from src.strategies import smc_sweep
    for raiz, cfg in (("GC", smc_sweep.ORO), ("NQ", smc_sweep.NASDAQ)):
        m1 = velas_1m(raiz)
        tramo = m1[(m1.index >= "2018-06-01") & (m1.index < "2019-06-01")]
        f = lambda v, c=cfg: smc_sweep.senales(v, c)  # noqa: E731
        assert len(f(tramo)) > 0          # el patrón es poco frecuente; basta con que haya señales
        assert comprobar(f, tramo, SABADOS_LARGO) == []


@hay_datos
def test_mnq_or_vwap_no_lookahead():
    from src.strategies import mnq_or_vwap
    m1 = velas_1m("NQ")
    tramo = m1[(m1.index >= "2019-02-01") & (m1.index < "2019-05-01")]
    assert len(mnq_or_vwap.senales(tramo)) > 10
    assert comprobar(mnq_or_vwap.senales, tramo, SABADOS) == []
