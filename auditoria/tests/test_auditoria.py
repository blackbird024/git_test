"""Pruebas de las herramientas de auditoría (métricas, bootstrap, variante de latencia)."""
import numpy as np
import pandas as pd
import pytest

from auditoria.src import metricas as mt


def _ops(netos, dias):
    t = pd.to_datetime(dias).tz_localize("America/New_York").tz_convert("UTC") + pd.Timedelta(hours=15)
    return pd.DataFrame({"neto": netos, "bruto": netos, "t_entrada": t - pd.Timedelta(hours=1), "t_salida": t})


def test_resumen_pf_t_dd_a_mano():
    o = _ops([100, -50, 100, -50], ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    d = mt.diario(o, pd.bdate_range("2024-01-02", "2024-01-05"))
    r = mt.resumen(o, d, 1000)
    assert r["profit_factor"] == 2.0 and r["expectativa_$"] == 25 and r["acierto_%"] == 50
    assert r["max_dd_$"] == -50
    x = pd.Series([100, -50, 100, -50.0])
    assert r["t_por_operacion"] == round(x.mean() / x.std(ddof=1) * 2, 2)


def test_diario_rellena_dias_sin_operaciones_y_agrupa_por_dia_de_salida():
    o = _ops([10, 20], ["2024-01-02", "2024-01-02"])
    d = mt.diario(o, pd.bdate_range("2024-01-01", "2024-01-05"))
    assert len(d) == 5 and d.loc["2024-01-02", "pnl"] == 30 and d.loc["2024-01-02", "n"] == 2 and d.pnl.sum() == 30


def test_ic_bloques_reproducible_y_contiene_la_media():
    rng = np.random.default_rng(1)
    d = pd.DataFrame({"pnl": rng.normal(5, 50, 500), "n": 1.0})
    a = mt.ic_bloques(d, 20, 2000, 7)
    b = mt.ic_bloques(d, 20, 2000, 7)
    assert a == b and a[0] < d.pnl.mean() < a[1]


def test_ic_bloques_mas_ancho_con_autocorrelacion():
    rng = np.random.default_rng(2)
    e = rng.normal(0, 1, 2000)
    ar = np.zeros(2000)
    for i in range(1, 2000):
        ar[i] = 0.8 * ar[i - 1] + e[i]
    d = pd.DataFrame({"pnl": ar, "n": 1.0})
    lo_b, hi_b = mt.ic_bloques(d, 20, 3000, 3)
    lo_i, hi_i = mt.ic_iid(d.pnl)
    assert (hi_b - lo_b) > 1.5 * (hi_i - lo_i)          # el IID infravalora la incertidumbre con dependencia


@pytest.mark.skipif(not __import__("pathlib").Path("data/processed/NQ_1M.parquet").exists(), reason="sin datos")
def test_variante_latencia_cero_reproduce_el_original():
    from src.data.datos import velas_1m
    from src.strategies import zona_ruido as z
    from auditoria.src import variantes_zr as v
    m1 = velas_1m("NQ")
    m1 = m1[(m1.index >= "2019-01-01") & (m1.index < "2019-07-01")]
    a, _ = z.backtest(m1, z.Config())
    b = v.backtest(m1, z.Config(), retardo=0)
    assert len(a) == len(b) > 50
    np.testing.assert_allclose(a.neto.to_numpy(), b.neto.to_numpy())
    assert (pd.to_datetime(a.t_entrada) == pd.to_datetime(b.t_entrada)).all()
    c = v.backtest(m1, z.Config(), retardo=1)
    assert (pd.to_datetime(c.t_entrada) >= pd.to_datetime(a.t_entrada).min()).all() and not np.allclose(c.neto.sum(), a.neto.sum())


def test_pesos_reescalados_igualan_la_volatilidad_de_la_zona():
    from auditoria.src import cartera as ca
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2015-01-01", periods=2000)
    d = pd.DataFrame({"zona": rng.normal(5, 100, 2000), "rsi2": rng.normal(5, 300, 2000)}, index=idx)
    corte = idx[1200]
    wz, wr = ca.pesos(d, corte, (1, 1))
    dev = d[d.index < corte]
    assert abs((wz * dev.zona + wr * dev.rsi2).std() - dev.zona.std()) < 1.0
    assert wz * dev.zona.std() == pytest.approx(wr * dev.rsi2.std(), rel=1e-2)       # igual presupuesto de riesgo


def test_simulacion_de_riesgo_reproducible_y_detencion():
    from auditoria.src import cartera as ca
    p = pd.Series(np.r_[np.full(50, -200.0), np.full(50, 100.0)])
    a = ca.simular_riesgo(p, 25000, 150, 1000, 10, 500, 100, 1)
    b = ca.simular_riesgo(p, 25000, 150, 1000, 10, 500, 100, 1)
    assert a == b
    assert a["max_dd_p95_$"] >= -1200                     # la detención corta la caída cerca del límite
    assert a["prob_detencion_por_caida_%"] > 0 and a["dias_al_año_sobre_limite_diario_media"] > 0


def test_clasificacion_segun_criterios():
    from auditoria.src.rechazadas import clasificar
    neg = {"operaciones": 500, "expectativa_$": -5, "IC95_bloques_$": (-9.0, -1.0)}
    assert clasificar(neg, neg) == "Evidencia negativa"
    peq = {"operaciones": 40, "expectativa_$": 10, "IC95_bloques_$": (-5.0, 20.0)}
    assert clasificar(peq, peq) == "No concluyente por muestra insuficiente"
    cero = {"operaciones": 800, "expectativa_$": 1, "IC95_bloques_$": (-3.0, 5.0)}
    assert clasificar(cero, cero).startswith("No concluyente (el IC")
    pos = {"operaciones": 800, "expectativa_$": 6, "IC95_bloques_$": (2.0, 10.0)}
    assert clasificar(pos, pos).startswith("Evidencia positiva")
    assert clasificar({"operaciones": 0}, {}) .startswith("No verificable")
