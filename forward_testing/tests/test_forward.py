"""Pruebas de integridad de FORWARD_TESTING v1.0. Se simula un forward con un inicio ficticio (01/06/2026) sobre datos
reales ya existentes y se provocan errores a propósito para comprobar que se detectan."""
import json

import numpy as np
import pandas as pd
import pytest

from forward_testing.src import comparar as CP
from forward_testing.src import congelado as CG
from forward_testing.src import datos as DT
from forward_testing.src import deriva as DV
from forward_testing.src import ea as EA
from forward_testing.src import integridad as IG
from forward_testing.src import teorico as TE
from src.data.datos import velas_1m

INICIO = pd.Timestamp("2026-06-01")
INICIO_UTC = INICIO.tz_localize("America/New_York").tz_convert("UTC")


@pytest.fixture(scope="module")
def m1():
    m = velas_1m("NQ")
    return m[(m.index >= "2025-01-01") & (m.index < "2026-07-16")]


@pytest.fixture(scope="module")
def fwd(m1):
    return TE.calcular(m1, INICIO)


def test_congelacion_intacta():
    assert CG.verificar() == []


def test_congelacion_detecta_cambios(tmp_path, monkeypatch):
    cfg = json.loads(CG.CONFIG.read_text(encoding="utf-8"))
    cfg["sha256"]["src/strategies/nq_rsi2.py"] = "0" * 64
    cfg["estrategias"]["RSI2"]["parametros"]["entrada"] = 25.0
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(CG, "CONFIG", ruta)
    monkeypatch.setattr(CG, "HUELLA", tmp_path / "c.sha256")
    (tmp_path / "c.sha256").write_text("x")
    p = " | ".join(CG.verificar())
    assert "ha cambiado después de congelarse" in p and "nq_rsi2.py ha cambiado" in p and "parámetros de RSI2" in p


def test_forward_simulado_pasa_la_integridad(fwd, m1):
    assert len(fwd["NOISE_ZONE"]) > 10
    for k in ("NOISE_ZONE", "RSI2"):
        assert IG.operaciones(fwd[k], m1, INICIO_UTC, k) == [], k


def test_campos_obligatorios(fwd):
    obligatorios = ["t_entrada_utc", "t_salida_utc", "estrategia", "direccion", "contrato", "precio_teorico_entrada",
                    "precio_real_entrada", "precio_teorico_salida", "precio_real_salida", "slippage_$", "comision_$",
                    "bruto_$", "neto_$", "duracion_min", "mae_pts", "mfe_pts", "sesion", "fecha_sesion", "VOL_ATR", "atr14"]
    for k in ("NOISE_ZONE", "RSI2"):
        if len(fwd[k]):
            assert set(obligatorios) <= set(fwd[k].columns), set(obligatorios) - set(fwd[k].columns)


def test_timestamps_utc_y_posteriores_al_inicio(fwd):
    for k in ("NOISE_ZONE", "RSI2"):
        o = fwd[k]
        if len(o):
            assert str(pd.DatetimeIndex(o.t_entrada_utc).tz) == "UTC"
            assert (pd.DatetimeIndex(o.t_entrada_utc) >= INICIO_UTC).all()


def test_sin_lookahead_append_only(m1, fwd):
    """Lo calculado con datos hasta el 01/07 se reproduce EXACTO al añadir dos semanas más de datos."""
    antes = TE.calcular(m1[m1.index < "2026-07-01"], INICIO)
    reg = pd.concat([antes["NOISE_ZONE"], antes["RSI2"]], ignore_index=True)
    ahora = pd.concat([fwd["NOISE_ZONE"], fwd["RSI2"]], ignore_index=True)
    assert IG.append_only(reg, ahora) == []


def test_append_only_detecta_revisiones(fwd):
    reg = fwd["NOISE_ZONE"].copy()
    nuevo = reg.copy()
    nuevo.loc[0, "neto_$"] += 5
    assert IG.append_only(reg, nuevo)


def test_detecta_operacion_imposible(fwd, m1):
    o = fwd["NOISE_ZONE"].copy()
    o.loc[0, "precio_teorico_entrada"] += 5000
    assert any("imposible" in p for p in IG.operaciones(o, m1, INICIO_UTC, "NOISE_ZONE"))


def test_detecta_duplicados(fwd, m1):
    o = pd.concat([fwd["NOISE_ZONE"], fwd["NOISE_ZONE"].iloc[:1]], ignore_index=True)
    assert any("duplicadas" in p for p in IG.operaciones(o, m1, INICIO_UTC, "NOISE_ZONE"))


def test_detecta_costes_mal_aplicados(fwd, m1):
    o = fwd["NOISE_ZONE"].copy()
    o.loc[0, "neto_$"] = o.loc[0, "bruto_sin_costes_$"]
    assert any("neto" in p for p in IG.operaciones(o, m1, INICIO_UTC, "NOISE_ZONE"))
    o = fwd["NOISE_ZONE"].copy()
    o.loc[0, "precio_real_entrada"] = o.loc[0, "precio_teorico_entrada"]
    assert any("deslizamiento" in p for p in IG.operaciones(o, m1, INICIO_UTC, "NOISE_ZONE"))


def test_zona_de_ruido_no_mantiene_de_noche(fwd, m1):
    o = fwd["NOISE_ZONE"].copy()
    o.loc[0, "t_salida_utc"] = o.loc[0, "t_salida_utc"] + pd.Timedelta(days=1)
    assert any("de noche" in p for p in IG.operaciones(o, m1, INICIO_UTC, "NOISE_ZONE"))


def test_rsi2_abierta_y_noche_contabilizada(m1):
    """Datos cortados justo después de una entrada del RSI(2): la operación queda ABIERTA (no se cuenta como cerrada) y
    las cerradas pueden durar varias sesiones (noche contabilizada en el P&L con precios ajustados)."""
    todas = TE.calcular(m1, pd.Timestamp("2025-09-01"))["RSI2"]
    assert len(todas) and (todas.sesiones >= 1).all()
    t = pd.Timestamp(todas.t_entrada_utc.iloc[-1])
    corto = TE.calcular(m1[m1.index < t + pd.Timedelta(hours=20)], pd.Timestamp("2025-09-01"))["RSI2"]
    assert corto.estado.iloc[-1] == "ABIERTA"
    assert (corto.estado == "ABIERTA").sum() == 1


def test_datos_faltantes_y_zona_horaria(m1):
    dia = pd.Timestamp("2026-07-01")
    ny = m1.index.tz_convert("America/New_York")
    hueco = (ny.normalize().tz_localize(None) == dia) & (ny.hour == 11)
    assert any(g == "GRAVE" for g, _ in DT.calidad_dia(m1[~hueco], dia))
    assert DT.calidad_dia(m1, dia) == []
    ingenuo = m1.tz_convert(None) if False else m1.copy()
    ingenuo.index = ingenuo.index.tz_localize(None)
    with pytest.raises(Exception):
        DT.calidad_dia(ingenuo, dia)


def test_deriva_estados_y_umbral_oficial():
    rng = np.random.default_rng(0)
    ref = {"NOISE_ZONE": pd.DataFrame({"neto": rng.normal(8, 60, 3000)})}
    b = DV.todas_las_bandas(ref, {"NOISE_ZONE": [20, 50, 100]})
    bien = {"NOISE_ZONE": pd.DataFrame({"neto_$": rng.normal(8, 60, 120)})}
    mal = {"NOISE_ZONE": pd.DataFrame({"neto_$": np.full(120, -40.0)})}
    of = {"NOISE_ZONE": {"ventana": 50, "media_$": -20.5}}
    assert not DV.evaluar(bien, b, of).estado.str.contains("ALERT").any()
    e = DV.evaluar(mal, b, of).set_index("ventana").estado
    assert e[50] == "ALERTA OFICIAL (informativa)" and e[20] in ("WARNING", "ALERT")
    poco = {"NOISE_ZONE": pd.DataFrame({"neto_$": [1.0] * 10})}
    assert DV.evaluar(poco, b, of).estado.str.contains("insuficiente").all()


def test_comparacion_backtest_forward():
    rng = np.random.default_rng(1)
    ref = pd.DataFrame({"neto": rng.normal(8, 60, 3000), "t_entrada": pd.Timestamp("2020-01-01", tz="UTC"),
                        "t_salida": pd.Timestamp("2020-01-01 01:00", tz="UTC")})
    fwd = pd.DataFrame({"neto_$": rng.normal(8, 60, 60), "duracion_min": 60.0})
    c = CP.comparar(ref, fwd, 50)
    assert "forward/backtest" in c["tabla"].columns and c["rango"]["concluyente"] and "dentro_de_rango" in c["rango"]
    assert not CP.comparar(ref, fwd.iloc[:10], 50)["rango"]["concluyente"]


def test_registro_del_ea_y_emparejamiento(tmp_path):
    p = tmp_path / "APEX_registro_v2.csv"
    p.write_text("hora_servidor,hora_NY,estrategia,accion,precio,bid_previo,ask_previo,spread_previo,deal,lotes,magic,motivo\n"
                 "2026.10.01 17:00:02,2026.10.01 10:00:02,Zona de ruido,COMPRAR,20001.0,19999.5,20000.5,1.0,11,2.00,290901,banda\n"
                 "2026.10.01 18:30:01,2026.10.01 11:30:01,Zona de ruido,CERRAR,20010.0,20010.5,20011.5,1.0,12,2.00,290901,trailing\n",
                 encoding="utf-8")
    ea, prob = EA.operaciones(EA.leer(p))
    assert prob == [] and len(ea) == 1
    r = ea.iloc[0]
    assert r.slippage_entrada_pts == pytest.approx(0.5) and r.slippage_salida_pts == pytest.approx(0.5)
    assert r["neto_$"] == pytest.approx(18.0)
    teo = pd.DataFrame([{"id": "NOISE_ZONE|x", "estrategia": "NOISE_ZONE", "direccion": "LARGO",
                         "t_entrada_ny": "2026-10-01 10:00", "neto_$": 20.0}])
    assert EA.emparejar(teo, ea).estado.iloc[0] == "emparejada"
