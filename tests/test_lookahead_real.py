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


@hay_datos
def test_gold_swing_simple_no_lookahead():
    from src.strategies import gold_swing_simple
    m1 = velas_1m("GC")
    tramo = m1[(m1.index >= "2018-01-01") & (m1.index < "2019-07-01")]
    s = gold_swing_simple.senales(tramo)
    assert len(s) > 3
    cortes = [pd.Timestamp(x, tz="UTC") for x in ("2018-04-14", "2018-08-11", "2018-11-10", "2019-03-09")]
    assert comprobar(gold_swing_simple.senales, tramo, cortes) == []


@hay_datos
def test_gold_swing_minimal_no_lookahead():
    from src.strategies import gold_swing_minimal
    m1 = velas_1m("GC")
    tramo = m1[(m1.index >= "2018-01-01") & (m1.index < "2018-10-01")]
    assert len(gold_swing_minimal.senales(tramo)) > 50
    cortes = [pd.Timestamp(x, tz="UTC") for x in ("2018-03-10", "2018-05-12", "2018-07-14", "2018-09-08")]
    assert comprobar(gold_swing_minimal.senales, tramo, cortes) == []


@hay_datos
def test_gold_london_false_break_no_lookahead():
    from src.strategies import gold_london_false_break
    m1 = velas_1m("GC")
    tramo = m1[(m1.index >= "2018-01-01") & (m1.index < "2018-10-01")]
    assert len(gold_london_false_break.senales(tramo)) > 20
    cortes = [pd.Timestamp(x, tz="UTC") for x in ("2018-03-10", "2018-05-12", "2018-07-14", "2018-09-08")]
    assert comprobar(gold_london_false_break.senales, tramo, cortes) == []


@hay_datos
def test_zona_ruido_no_lookahead_and_daily_levels_match_backtest():
    import datetime as dt
    from src.strategies import zona_ruido
    m1 = velas_1m("NQ")
    tramo = m1[(m1.index >= "2019-01-01") & (m1.index < "2019-07-01")]
    assert len(zona_ruido.senales(tramo)) > 50
    assert comprobar(zona_ruido.senales, tramo, SABADOS) == []
    # La herramienta diaria, con datos HASTA la víspera, da la misma sigma que usa el backtest ese día
    dia = dt.date(2019, 5, 15)
    _, _, sigma = zona_ruido.preparar(tramo, zona_ruido.Config())
    hasta = tramo[tramo.index < pd.Timestamp("2019-05-15 04:00", tz="UTC")]
    n = zona_ruido.niveles(hasta)
    esperado = [sigma.loc[dia, m - 1] * 100 for m in zona_ruido.Config().chequeos]
    assert n["ultima_sesion"] == dt.date(2019, 5, 14)
    assert n["tabla"]["sigma_%"].round(10).tolist() == pd.Series(esperado).round(10).tolist()
