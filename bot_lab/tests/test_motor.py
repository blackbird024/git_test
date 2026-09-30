"""Pruebas del motor del laboratorio con velas de juguete (1 min, 10:00 NY en adelante: deslizamiento de 1 tick)."""
import numpy as np
import pandas as pd
import pytest

from bot_lab.core.datos import Contexto
from bot_lab.core.motor import simular

TICK = 0.25


def ctx_de(velas, inicio="2020-06-01 14:00", excluir=frozenset()):
    """velas: lista de (open, high, low, close)."""
    t = pd.date_range(inicio, periods=len(velas), freq="1min", tz="UTC")
    df = pd.DataFrame(velas, columns=["open", "high", "low", "close"], index=t)
    df["volume"] = 100
    df["instrument_id"] = 1
    return Contexto(df, excluir)


def orden(**k):
    return pd.DataFrame([k])


PLANO = [(100, 101, 99, 100)] * 10


def test_entrada_en_apertura_siguiente_con_deslizamiento():
    v = PLANO.copy()
    v[1] = (102, 103, 101, 102)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=90.0, i_fin=5))
    assert ops.entrada[0] == 102 + TICK
    assert ops.i_entrada[0] == 1


def test_stop_y_objetivo_en_la_misma_vela_cuenta_stop():
    v = PLANO.copy()
    v[2] = (100, 110, 90, 100)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=95.0, obj=105.0, i_fin=8))
    assert ops.motivo[0] == "stop"
    assert ops.salida[0] == 95 - TICK


def test_hueco_mas_alla_del_stop_sale_en_la_apertura():
    v = PLANO.copy()
    v[3] = (90, 91, 89, 90)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=95.0, i_fin=8))
    assert ops.salida[0] == 90 - TICK and ops.motivo[0] == "stop"


def test_objetivo_limite_exacto_sin_deslizamiento():
    v = PLANO.copy()
    v[3] = (100, 106, 99.5, 105)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=95.0, obj=105.0, i_fin=8))
    assert ops.motivo[0] == "objetivo" and ops.salida[0] == 105.0


def test_objetivo_en_R_desde_el_precio_real_de_entrada():
    v = PLANO.copy()
    v[4] = (100, 120, 99.5, 110)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=95.0, r_obj=2.0, i_fin=8))
    ent = 100 + TICK
    assert ops.salida[0] == pytest.approx(ent + 2 * (ent - 95))


def test_salida_por_tiempo_en_la_apertura():
    ctx = ctx_de(PLANO)
    ops = simular(ctx, orden(i_sig=0, dir=-1, stop=110.0, i_fin=6))
    assert ops.motivo[0] == "tiempo" and ops.i_salida[0] == 6 and ops.salida[0] == 100 + TICK


def test_una_posicion_a_la_vez():
    ctx = ctx_de(PLANO)
    o = pd.DataFrame([{"i_sig": 0, "dir": 1, "stop": 90.0, "i_fin": 6}, {"i_sig": 3, "dir": 1, "stop": 90.0, "i_fin": 8},
                      {"i_sig": 6, "dir": 1, "stop": 90.0, "i_fin": 9}])
    ops = simular(ctx, o)
    assert list(ops.orden) == [0, 2]


def test_orden_stop_oco_y_en_la_vela_de_llenado_solo_stop():
    v = PLANO.copy()
    v[2] = (100, 103, 100.5, 102)    # rompe 102 -> compra; el objetivo 1R (104) no se evalúa en esta vela
    v[3] = (102, 104.5, 101.5, 104)  # objetivo
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, tipo=1, nivel_l=102.0, stop_l=100.0, nivel_c=98.0, stop_c=100.0, r_obj=1.0, i_fin=9))
    ent = 102 + TICK
    assert ops.direccion[0] == 1 and ops.entrada[0] == ent and ops.i_entrada[0] == 2
    assert ops.motivo[0] == "objetivo" and ops.i_salida[0] == 3


def test_orden_stop_con_stop_en_la_vela_de_llenado():
    v = PLANO.copy()
    v[2] = (100, 103, 97, 98)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, tipo=1, nivel_l=102.0, stop_l=99.0, i_fin=9))
    assert ops.motivo[0] == "stop" and ops.i_salida[0] == 2


def test_orden_stop_que_no_se_llena_no_opera():
    ctx = ctx_de(PLANO)
    assert simular(ctx, orden(i_sig=0, tipo=1, nivel_l=150.0, stop_l=99.0, i_fin=9)).empty


def test_trailing_mueve_el_stop():
    v = [(100, 101, 99, 100), (100, 101, 99.5, 101), (101, 106, 100.5, 105), (105, 110, 104.5, 109),
         (109, 109.5, 104, 104.5), (104, 105, 103, 104)]
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop=95.0, trail=3.0, i_fin=6))
    # máximo cierre 109 -> stop 106; la vela 4 baja a 104 -> sale en 106 - 1 tick
    assert ops.motivo[0] == "trailing" and ops.salida[0] == 106 - TICK


def test_objetivo_vwap_dinamico():
    v = [(100, 100.5, 99.5, 100)] * 3 + [(96, 96.5, 95.5, 96)] * 3 + [(96, 101, 95.8, 100)] + [(100, 100.5, 99.5, 100)] * 3
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=4, dir=1, stop=90.0, obj_vwap=True, i_fin=9))
    vw = ctx.vwap_previo("rth")[6]
    assert ops.motivo[0] == "objetivo" and ops.i_salida[0] == 6 and ops.salida[0] == pytest.approx(max(vw, 96))


def test_costes_multiplicados():
    ctx = ctx_de(PLANO)
    a = simular(ctx, orden(i_sig=0, dir=1, stop=90.0, i_fin=6))
    b = simular(ctx, orden(i_sig=0, dir=1, stop=90.0, i_fin=6), mult=2.0)
    assert a.neto[0] == pytest.approx(-2 * TICK * 2 - 2.0)
    assert b.neto[0] == pytest.approx(-4 * TICK * 2 - 4.0)


def test_entrada_mas_alla_del_stop_se_descarta():
    ctx = ctx_de(PLANO)
    assert simular(ctx, orden(i_sig=0, dir=1, stop=100.5, i_fin=6)).empty


def test_maximo_por_sesion():
    ctx = ctx_de(PLANO)
    o = pd.DataFrame([{"i_sig": 0, "dir": 1, "stop": 90.0, "i_fin": 2}, {"i_sig": 3, "dir": 1, "stop": 90.0, "i_fin": 5}])
    assert len(simular(ctx, o, max_ses=1)) == 1
    assert len(simular(ctx, o)) == 2


def test_stop_por_distancia_desde_el_llenado_y_mae_mfe():
    v = PLANO.copy()
    v[2] = (100, 103, 98, 102)
    ctx = ctx_de(v)
    ops = simular(ctx, orden(i_sig=0, dir=1, stop_dist=5.0, i_fin=5))
    ent = 100 + TICK
    assert ops.riesgo_pts[0] == pytest.approx(5.0)
    assert ops.mfe_pts[0] == pytest.approx(103 - ent) and ops.mae_pts[0] == pytest.approx(ent - 98)


def test_motor_coincide_con_el_motor_antiguo():
    """Misma operación con src/engine/ejecucion.ejecutar (reglas del proyecto)."""
    from src.engine.costes import Costes
    from src.engine.ejecucion import ejecutar
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 0.5, 60))
    o = np.r_[100, c[:-1]]
    h = np.maximum(o, c) + 0.3
    l = np.minimum(o, c) - 0.3
    v = list(zip(o, h, l, c))
    ctx = ctx_de(v)
    velas = ctx.m1[["open", "high", "low", "close"]]
    viejo = ejecutar(velas, 5, 1, stop=c[5] - 2, objetivo=c[5] + 3, contratos=1, t_limite=velas.index[50],
                     tick=TICK, valor_punto=2.0, costes=Costes())
    nuevo = simular(ctx, orden(i_sig=5, dir=1, stop=c[5] - 2, obj=c[5] + 3, i_fin=50))
    assert nuevo.salida[0] == pytest.approx(viejo.salida) and nuevo.neto[0] == pytest.approx(viejo.neto)
