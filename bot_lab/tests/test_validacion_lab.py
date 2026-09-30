"""Pruebas de validación, cartera, tamaño, prop firm y clasificación con datos sintéticos."""
import numpy as np
import pandas as pd
import pytest

from bot_lab.core import metricas as M
from bot_lab.core.datos import tramo_de_fecha
from bot_lab.portfolio import prop_firm, sizing
from bot_lab.validation import clasificacion, montecarlo, regimenes, walk_forward
from bot_lab.validation.protocolo import seleccionar

CFG = {"clasificacion": {"pf_a": 1.15, "min_ops": 200, "min_ops_baja_frecuencia": 100, "estabilidad_a": 0.7,
                         "estabilidad_fragil": 0.5, "anios_positivos": 0.6, "prob_anio_negativo": 0.3, "calmar_min": 0.33}}


def ops_sint(n=300, media=5.0, sd=50.0, semilla=0, desde="2016-01-04"):
    rng = np.random.default_rng(semilla)
    t = pd.date_range(desde, periods=n, freq="B", tz="UTC") + pd.Timedelta(hours=15)
    x = rng.normal(media, sd, n)
    return pd.DataFrame({"t_entrada": t, "t_salida": t + pd.Timedelta(minutes=30), "neto": x, "bruto": x + 2,
                         "r": x / 50, "direccion": 1, "riesgo_pts": 25.0, "comision": 2.0,
                         "mae_pts": 10.0, "mfe_pts": 12.0})


def test_particion_por_fecha():
    f = pd.to_datetime(["2015-06-01", "2022-01-14", "2022-01-18", "2024-05-22", "2024-05-23", "2026-09-28"])
    assert list(tramo_de_fecha(f)) == [0, 0, 1, 1, 2, 2]


def test_metricas_completas_coherentes():
    o = ops_sint()
    ses = pd.DatetimeIndex(pd.to_datetime(o.t_entrada).dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None))
    m = M.completas(o, ses)
    assert m["operaciones"] == 300
    assert m["neto_$"] == pytest.approx(round(o.neto.sum(), 0))
    assert m["ganancia_bruta_$"] + m["perdida_bruta_$"] == pytest.approx(m["neto_$"], abs=2)
    assert m["max_dd_$"] <= 0 and m["dd_medio_$"] >= m["max_dd_$"]
    assert m["MAE_medio_R"] == pytest.approx(0.4)


def test_seleccion_regla_fija_y_empate_a_favor_de_la_base():
    t = pd.DataFrame({"operaciones": [200, 200, 50, 300], "t": [2.0, 2.2, 5.0, 1.0], "control": [False, False, False, True]},
                     index=["base", "otra", "poca_muestra", "control"])
    assert seleccionar(t, "base", 100, 0.3)[0] == "base"
    t.loc["otra", "t"] = 2.5
    assert seleccionar(t, "base", 100, 0.3)[0] == "otra"


def test_walk_forward_reselecciona_solo_con_el_pasado():
    buena = ops_sint(800, media=10, sd=5, semilla=1)
    mala = ops_sint(800, media=-10, sd=5, semilla=2)
    r = walk_forward.ejecutar({"buena": buena, "mala": mala}, set(), "mala", "buena", pd.Timestamp("2016-01-01"),
                              pd.Timestamp("2019-01-01"), 12, 3, 20, 0.3)
    assert (r["ventanas"].elegida == "buena").all()
    assert r["reseleccion"]["expectativa_$"] > 0 and r["reseleccion"]["ventanas_positivas_%"] == 100


def test_montecarlo_serie_positiva_constante():
    p = pd.Series(10.0, index=pd.bdate_range("2020-01-01", periods=500))
    d = montecarlo.distribucion(p, 25000, 20, 200, 252, 1)
    assert d["prob_año_negativo_%"] == 0 and d["max_dd_p95_$"] == 0 and d["P&L_año_p50_$"] == 2520


def test_prop_firm_aprueba_y_quema():
    p = pd.Series(1000.0, index=pd.bdate_range("2020-01-01", periods=100))
    assert prop_firm.simular(p, 1, 50000, 1000, 2500, 3000, 50, 20, 50, 1)["prob_aprobar_%"] == 100
    q = pd.Series(-900.0, index=p.index)
    assert prop_firm.simular(q, 1, 50000, 1000, 2500, 3000, 50, 20, 50, 1)["prob_quemar_%"] == 100


def test_limite_diario_corta_la_perdida_del_dia():
    q = pd.Series(-5000.0, index=pd.bdate_range("2020-01-01", periods=30))
    r = prop_firm.simular(q, 1, 50000, 1000, 2500, 3000, 30, 5, 20, 1)
    assert r["prob_quemar_%"] == 100


def test_tamano_por_riesgo_contratos_enteros_y_maximo():
    o = ops_sint(10)
    o["riesgo_pts"] = [5, 10, 25, 50, 100, 200, 300, 400, 500, 1000.0]
    s = sizing.aplicar(o, 25000, 0.5, 10)
    riesgo_1 = o.riesgo_pts * 2 + 2
    esperado = np.floor(125 / riesgo_1).clip(0, 10)
    assert list(s.contratos) == list(esperado[esperado > 0])
    assert s.contratos.max() <= 10


def test_clasificacion():
    base = {"metricas": {"profit_factor": 1.3, "expectativa_$": 10, "operaciones": 500, "frac_años_positivos": 0.8,
                         "neto_anual_$": 3000, "max_dd_$": -4000},
            "IC95_bloques_$": (2.0, 18.0), "walk_forward": {"reseleccion": {"expectativa_$": 5, "ventanas_positivas_%": 60}},
            "estabilidad": {"estabilidad": 0.8}, "costes": {"STRESS_1": {"expectativa_$": 4}},
            "montecarlo": {"prob_año_negativo_%": 10}, "test": {"expectativa_$": 3}}
    assert clasificacion.clase(base, CFG, False)[0].startswith("A")
    fragil = {**base, "costes": {"STRESS_1": {"expectativa_$": -1}}}
    assert clasificacion.clase(fragil, CFG, False)[0].startswith("D")
    poca = {**base, "metricas": {**base["metricas"], "operaciones": 80}}
    assert clasificacion.clase(poca, CFG, False)[0].startswith("C")
    sin_test = {**base, "test": {"expectativa_$": -2}}
    assert clasificacion.clase(sin_test, CFG, False)[0].startswith("B")


def test_franjas_horarias():
    m = np.array([18 * 60 + 5, 2 * 60, 4 * 60, 9 * 60, 9 * 60 + 45, 11 * 60, 12 * 60, 15 * 60, 16 * 60 + 30])
    assert list(regimenes.franja(m)) == ["noche", "noche", "Londres", "pre-apertura/solape", "apertura NY", "mañana NY",
                                         "mediodía NY", "tarde NY", "cierre/otras"]
