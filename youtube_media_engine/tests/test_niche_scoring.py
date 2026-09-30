import copy

import pytest

from src.research import niche_scoring as ns


@pytest.fixture(scope="module")
def cargado():
    return ns.cargar()


def test_datos_reales_validan(cargado):
    pesos, datos = cargado
    assert len(datos["categorias"]) == 7


def test_puntuacion_extremos():
    pesos = {"a": 60.0, "b": 40.0}
    datos = {"fuentes": {"S1": {}}, "categorias": {
        "max": {"nombre": "max", "puntuaciones": {"a": {"valor": 5, "evidencia": "fuente:S1"}, "b": {"valor": 5, "evidencia": "juicio"}}},
        "min": {"nombre": "min", "puntuaciones": {"a": {"valor": 1, "evidencia": "juicio"}, "b": {"valor": 1, "evidencia": "juicio"}}}}}
    r = {x.clave: x for x in ns.puntuar(pesos, datos)}
    assert r["max"].puntuacion == 100 and r["min"].puntuacion == 0
    assert r["max"].pct_juicio == 40 and r["min"].pct_juicio == 100


def test_pesos_deben_sumar_100(cargado):
    pesos, datos = cargado
    malos = dict(pesos, demanda=pesos["demanda"] + 1)
    with pytest.raises(ValueError, match="sumar 100"):
        ns.validar(malos, datos)


def test_evidencia_inventada_se_rechaza(cargado):
    pesos, datos = cargado
    d = copy.deepcopy(datos)
    d["categorias"]["naturaleza"]["puntuaciones"]["coste"]["evidencia"] = "fuente:S99"
    with pytest.raises(ValueError, match="S99"):
        ns.validar(pesos, d)


def test_criterio_que_falta_se_rechaza(cargado):
    pesos, datos = cargado
    d = copy.deepcopy(datos)
    del d["categorias"]["naturaleza"]["puntuaciones"]["coste"]
    with pytest.raises(ValueError, match="criterios distintos"):
        ns.validar(pesos, d)


def test_sensibilidad_reproducible_y_coherente(cargado):
    pesos, datos = cargado
    a, b = ns.sensibilidad(pesos, datos, n=300), ns.sensibilidad(pesos, datos, n=300)
    assert a == b
    assert abs(sum(v["primero_%"] for v in a.values()) - 100) < 0.5
