"""Pruebas de las estrategias del laboratorio sobre datos reales de NQ (2018-2019): look-ahead por truncamiento,
ventanas horarias, una posición a la vez, costes y casos límite."""
import numpy as np
import pandas as pd
import pytest

from bot_lab.core.datos import Contexto
from bot_lab.core.motor import normalizar
from bot_lab.strategies import (momentum, orb, overnight, previous_day, pullback, regime, rsi2_extremo, time_of_day,
                                trend_following, vwap_mean_reversion)
from src.data.datos import velas_1m

INTRADIA = [vwap_mean_reversion, orb, trend_following, momentum, pullback, regime, previous_day, overnight, time_of_day]
VENTANAS = {  # minutos NY en que puede ENTRAR cada estrategia (la entrada es 1 min después de la señal)
    "13": (600, 906), "15": (600, 916), "16": (585, 936), "17": (600, 906), "19": (600, 906), "23": (575, 906),
    "24": (575, 721),
}


@pytest.fixture(scope="module")
def m1():
    m = velas_1m("NQ")
    return m[(m.index >= "2018-01-01") & (m.index < "2019-07-01")]


@pytest.fixture(scope="module")
def ctx(m1):
    return Contexto(m1)


def firma(mod, c, p):
    o = mod.ordenes(c, p)
    if len(o) == 0:
        return pd.DataFrame(columns=["t", "dir"])
    o = normalizar(o)
    cols = [k for k in ("dir", "stop", "stop_dist", "nivel_l", "nivel_c", "stop_l", "stop_c", "r_obj", "obj", "trail")]
    f = o[cols].copy()
    f.insert(0, "t", c.t[o.i_sig.to_numpy()])
    return f.round(6).reset_index(drop=True)


@pytest.mark.parametrize("mod", INTRADIA, ids=lambda m: m.BOT)
def test_sin_lookahead_por_truncamiento(mod, m1, ctx):
    corte = pd.Timestamp("2019-02-15", tz="UTC")
    for nombre, p in mod.VARIANTES.items():
        completa = firma(mod, ctx, p)
        parcial = firma(mod, Contexto(m1[m1.index < corte]), p)
        margen = corte - pd.Timedelta(days=1)          # la última sesión truncada puede no estar completa
        a = completa[completa.t < margen].reset_index(drop=True)
        b = parcial[parcial.t < margen].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"{nombre}")


def test_rsi2_extremo_sin_lookahead(m1):
    m = velas_1m("NQ")
    m = m[(m.index >= "2016-01-01") & (m.index < "2020-01-01")]
    corte = pd.Timestamp("2019-03-01", tz="UTC")
    for nombre, p in rsi2_extremo.VARIANTES.items():
        a = rsi2_extremo.ejecutar(Contexto(m), p)
        b = rsi2_extremo.ejecutar(Contexto(m[m.index < corte]), p)
        a = a[a.t_salida < corte - pd.Timedelta(days=3)].reset_index(drop=True)
        b = b[b.t_salida < corte - pd.Timedelta(days=3)].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, obj=nombre)


@pytest.mark.parametrize("mod", [m for m in INTRADIA if m.BOT in VENTANAS], ids=lambda m: m.BOT)
def test_entradas_dentro_de_su_ventana_y_salida_antes_del_cierre(mod, ctx):
    lo, hi = VENTANAS[mod.BOT]
    for p in mod.VARIANTES.values():
        o = mod.ejecutar(ctx, p)
        if len(o) == 0:
            continue
        t = pd.DatetimeIndex(o.t_entrada).tz_convert("America/New_York")
        m = t.hour * 60 + t.minute
        assert ((m >= lo) & (m < hi)).all()
        s = pd.DatetimeIndex(o.t_salida).tz_convert("America/New_York")
        assert ((s.hour * 60 + s.minute) <= 956).all() and (s.date == t.date).all()


@pytest.mark.parametrize("mod", INTRADIA, ids=lambda m: m.BOT)
def test_una_posicion_a_la_vez_y_sin_duplicados(mod, ctx):
    for p in list(mod.VARIANTES.values())[:3]:
        o = mod.ejecutar(ctx, p)
        if len(o) < 2:
            continue
        assert (o.i_entrada.to_numpy()[1:] > o.i_salida.to_numpy()[:-1]).all()
        assert not o.duplicated(["t_entrada"]).any()


@pytest.mark.parametrize("mod", INTRADIA + [rsi2_extremo], ids=lambda m: m.BOT)
def test_costes_x2_empeoran_cada_operacion(mod, ctx):
    p = mod.VARIANTES[mod.BASE]
    a, b = mod.ejecutar(ctx, p), mod.ejecutar(ctx, p, mult=2.0)
    if len(a) == 0:
        return
    comun = a.merge(b, on="t_entrada", suffixes=("", "_x2"))
    assert len(comun) > 0.8 * len(a)
    assert (comun.neto_x2 <= comun.neto + 1e-9).all()


def test_stop_del_orb_es_el_lado_opuesto(ctx):
    o = orb.ordenes(ctx, orb.VARIANTES[orb.BASE])
    assert (o.stop_l == o.nivel_c).all() and (o.stop_c == o.nivel_l).all()
    assert (o.nivel_l > o.nivel_c).all()


def test_datos_insuficientes_no_rompen(m1):
    c = Contexto(m1[m1.index < "2018-01-03 20:00"])
    for mod in INTRADIA:
        for p in mod.VARIANTES.values():
            o = mod.ejecutar(c, p)
            assert isinstance(o, pd.DataFrame)


def test_sin_volumen_no_hay_vwap_ni_senales_de_vwap(m1):
    m = m1[m1.index < "2018-02-01"].copy()
    m["volume"] = 0
    c = Contexto(m)
    assert np.isnan(c.vwap_rth[0]).all()
    assert len(vwap_mean_reversion.ordenes(c, vwap_mean_reversion.VARIANTES[vwap_mean_reversion.BASE])) == 0


def test_nan_en_precios_no_genera_operaciones_absurdas(m1):
    m = m1[m1.index < "2018-03-01"].copy()
    m.iloc[5000:5010, m.columns.get_indexer(["open", "high", "low", "close"])] = np.nan
    c = Contexto(m)
    for mod in (momentum, trend_following, vwap_mean_reversion):
        o = mod.ejecutar(c, mod.VARIANTES[mod.BASE])
        assert np.isfinite(o.neto).all()


def test_deriva_nocturna_excluye_cambios_de_contrato(ctx):
    o = time_of_day.ordenes(ctx, time_of_day.VARIANTES["21.1 largo 18:00→09:25 NY"])
    assert (ctx.desfase[o.i_sig.to_numpy() + 1] == ctx.desfase[o.i_fin.to_numpy()]).all()


def test_indicadores_ajustados_no_saltan_en_el_roll(ctx):
    k = np.flatnonzero(np.diff(ctx.desfase) != 0) + 1
    assert len(k) > 0
    salto_real = np.abs(ctx.O[k] - ctx.C[k - 1])
    salto_aj = np.abs((ctx.O[k] - ctx.desfase[k]) - (ctx.C[k - 1] - ctx.desfase[k - 1]))
    assert (salto_aj < 1e-9).all() and (salto_real > 0).all()
