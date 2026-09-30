from datetime import date

import pytest

from src.core import projects, store
from src.ideation import topics


@pytest.fixture
def carpetas(tmp_path):
    t, p = tmp_path / "topics", tmp_path / "projects"
    t.mkdir()
    p.mkdir()
    return t, p


def test_temas_reales_son_validos():
    ts = topics.todos()
    assert len(ts) >= 8
    assert len({t["id"] for t in ts}) == len(ts)


def test_nuevo_asigna_id_consecutivo(carpetas):
    t, _ = carpetas
    a = topics.nuevo("A", "¿A?", carpeta=t)
    b = topics.nuevo("B", "¿B?", carpeta=t)
    assert (a["id"], b["id"]) == ("T0001", "T0002")


def test_no_se_investiga_sin_fuentes(carpetas):
    t, _ = carpetas
    topics.nuevo("A", "¿A?", carpeta=t)
    with pytest.raises(topics.ErrorTema, match="sin ninguna fuente"):
        topics.cambiar_estado("T0001", "estado_investigacion", "investigado", carpeta=t)
    assert topics.cargar("T0001", t)["estado_investigacion"] == "sin_investigar"      # no se guardó


def test_no_se_produce_sin_investigar(carpetas):
    t, _ = carpetas
    topics.nuevo("A", "¿A?", carpeta=t)
    with pytest.raises(topics.ErrorTema, match="sin estar 'investigado'"):
        topics.cambiar_estado("T0001", "estado_produccion", "guion", carpeta=t)


def test_historial_registra_cambios(carpetas):
    t, _ = carpetas
    topics.nuevo("A", "¿A?", carpeta=t, hoy=date(2026, 1, 1))
    d = store.leer(topics.ruta("T0001", t))
    d["evidencia"] = [{"titulo": "x", "url": "https://example.org"}]
    store.escribir(topics.ruta("T0001", t), d)
    r = topics.cambiar_estado("T0001", "estado_investigacion", "investigado", nota="ok", carpeta=t, hoy=date(2026, 1, 2))
    assert r["historial"][-1] == {"fecha": "2026-01-02", "cambio": "estado_investigacion: sin_investigar -> investigado",
                                  "nota": "ok"}


def test_evidencia_sin_url_se_rechaza(carpetas):
    t, _ = carpetas
    topics.nuevo("A", "¿A?", carpeta=t)
    d = store.leer(topics.ruta("T0001", t))
    d["evidencia"] = [{"titulo": "sin url"}]
    with pytest.raises(topics.ErrorTema, match="url"):
        topics.validar(d)


def test_proyecto_carpetas_y_no_duplicado(carpetas):
    t, p = carpetas
    topics.nuevo("A", "¿A?", carpeta=t)
    m = projects.crear("T0001", raiz=p, carpeta_temas=t)
    assert m["id"] == "V0001"
    assert all((p / "V0001" / c).is_dir() for c in projects.CARPETAS)
    with pytest.raises(projects.ErrorProyecto, match="ya tiene"):
        projects.crear("T0001", raiz=p, carpeta_temas=t)


def test_paso_no_se_repite_si_entradas_iguales(carpetas):
    t, p = carpetas
    topics.nuevo("A", "¿A?", carpeta=t)
    projects.crear("T0001", raiz=p, carpeta_temas=t)
    h = projects.huella("guion v1", {"voz": "es_MX"})
    assert not projects.hecho("V0001", "voz", h, raiz=p)
    projects.registrar("V0001", "voz", h, raiz=p, coste_usd=0)
    assert projects.hecho("V0001", "voz", h, raiz=p)
    assert not projects.hecho("V0001", "voz", projects.huella("guion v2", {"voz": "es_MX"}), raiz=p)


def test_escritura_atomica_no_deja_temporales(tmp_path):
    store.escribir(tmp_path / "a.yaml", {"x": 1})
    assert [f.name for f in tmp_path.iterdir()] == ["a.yaml"]
