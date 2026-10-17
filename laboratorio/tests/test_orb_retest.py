"""Tests de MNQ_ORB_RETEST_v1 con sesiones sintéticas de resultado conocido."""
import numpy as np
import pandas as pd
import pytest

from data.loaders import Session
from orb_retest.config import BASELINE, COST_SCENARIOS, Config, Risk
from orb_retest.engine import run, size_and_account
from orb_retest.execution import contracts_for, round_tp, simulate
from orb_retest.signals import detect, opening_range

ST = BASELINE.strategy
C = COST_SCENARIOS["base"]
T = 0.25


def flat(price=105.0, n=390):
    m = np.full((n, 5), price, float)
    m[:, 4] = 100
    return m


def with_or(m, hi=110.0, lo=100.0):
    m[3, 1] = hi
    m[7, 2] = lo
    return m


def bar5(m, b, o, h, l, c):
    """La vela de 5 min b queda exactamente (o, h, l, c); los minutos siguientes del bloque se quedan en c."""
    k = 5 * b
    m[k] = (o, h, l, c, 100)
    for j in range(k + 1, k + 5):
        m[j, :4] = c
    m[k + 5:, :4] = c
    return m


def long_setup():
    m = with_or(flat())
    bar5(m, 3, 109, 112.5, 108.5, 112)        # 9:45 ruptura: cierra 112 > 110
    bar5(m, 4, 111, 112.5, 110.0, 112)        # 9:50 retesteo: mínimo 110 (en el ORH), cierra 112 > 111 (alcista)
    return m


def test_opening_range():
    assert opening_range(with_or(flat()), ST)[:2] == (110.0, 100.0)


def test_rango_incompleto():
    m = with_or(flat())
    m[2:4] = np.nan
    assert detect(m, 390, ST)[1] == "rango_incompleto"


def test_mecha_sin_cierre_no_es_ruptura():
    m = with_or(flat())
    bar5(m, 3, 108, 113, 107, 109)             # mecha a 113, cierre dentro
    sig, why = detect(m, 390, ST)
    assert sig is None and why == "sin_ruptura"


def test_ruptura_y_retesteo_largo():
    sig, why = detect(long_setup(), 390, ST)
    assert why == "senal" and sig.side == 1 and sig.breakout_bar == 3 and sig.retest_bar == 4
    assert sig.signal_k == 25                   # se conoce al cierre de la vela de 9:50 (minuto 25 = 9:55)


def test_retesteo_fuera_de_tolerancia():
    m = with_or(flat())
    bar5(m, 3, 109, 112.5, 108.5, 112)
    bar5(m, 4, 111, 112.5, 109.25, 112)       # mínimo 3 ticks por debajo del ORH (tolerancia 2)
    bar5(m, 5, 112, 113, 111.5, 113)          # no vuelve a la zona
    bar5(m, 6, 113, 114, 112, 114)
    assert detect(m, 390, ST)[1] == "sin_retesteo_valido"


def test_retesteo_bajista_no_confirma():
    m = with_or(flat())
    bar5(m, 3, 109, 112.5, 108.5, 112)
    bar5(m, 4, 112.5, 112.5, 110.25, 111)     # toca la zona pero cierra por debajo de su apertura
    bar5(m, 5, 111, 114, 111, 114)
    bar5(m, 6, 114, 115, 114, 115)
    assert detect(m, 390, ST)[1] == "sin_retesteo_valido"


def test_ventana_de_retesteo_caduca():
    m = with_or(flat())
    bar5(m, 3, 109, 112.5, 108.5, 112)
    for b in (4, 5, 6):
        bar5(m, b, 112, 113, 111.5, 112.5)    # no vuelven a la zona
    bar5(m, 7, 111, 112.5, 110.0, 112)        # retesteo válido, pero en la 4.ª vela
    assert detect(m, 390, ST)[1] == "sin_retesteo_valido"


def test_corto():
    m = with_or(flat())
    bar5(m, 3, 101, 101.5, 97.5, 98)
    bar5(m, 4, 99, 100.25, 97.5, 98)          # máximo 1 tick sobre el ORL, cierra < ORL y < apertura
    sig, why = detect(m, 390, ST)
    assert why == "senal" and sig.side == -1
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.sl == 100.5                     # máximo de la vela de retesteo + 1 tick


def test_entrada_despues_del_cierre_de_confirmacion():
    m = long_setup()
    m[25, 0] = 113.0                          # apertura del minuto siguiente a la confirmación
    sig, _ = detect(m, 390, ST)
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.entry_k == 25 and tr.entry == 113.0 + C.slip_ticks_entry * T   # no el cierre (112)
    assert tr.sl == 109.75                    # mínimo del retesteo (110) − 1 tick
    assert tr.r_pts == pytest.approx(113.25 - 109.75)
    assert tr.tp == round_tp(113.25 + 2 * 3.5, 1, T) == 120.25


def test_redondeo_tp():
    assert round_tp(100.1, 1, T) == 100.25 and round_tp(100.1, -1, T) == 100.0


def test_tp_exige_cruce():
    m = long_setup()
    sig, _ = detect(m, 390, ST)
    tr0, _ = simulate(sig, m, 390, ST, C)
    m[40, 1] = tr0.tp                         # toca el TP sin cruzarlo
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.reason == "tiempo"
    m[41, 1] = tr0.tp + T                     # lo cruza 1 tick
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.reason == "tp" and tr.exit == tr0.tp and tr.exit_k == 41


def test_sl_y_tp_en_la_misma_vela():
    m = long_setup()
    sig, _ = detect(m, 390, ST)
    tr0, _ = simulate(sig, m, 390, ST, C)
    m[30, 1] = tr0.tp + 5
    m[30, 2] = tr0.sl - 1
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.reason == "sl" and tr.ambiguous and tr.exit == tr0.sl - C.slip_ticks_stop * T


def test_hueco_atraviesa_stop():
    m = long_setup()
    sig, _ = detect(m, 390, ST)
    m[30, 0] = m[30, 1] = m[30, 2] = m[30, 3] = 105.0
    tr, _ = simulate(sig, m, 390, ST, C)
    assert tr.reason == "sl_hueco" and tr.exit == 105.0 - C.slip_ticks_stop * T


def test_entrada_al_otro_lado_del_stop():
    m = long_setup()
    m[25, 0] = 109.0                          # abre por debajo del SL (109.75)
    sig, _ = detect(m, 390, ST)
    tr, why = simulate(sig, m, 390, ST, C)
    assert tr is None and why == "entrada_al_otro_lado_del_stop"


def test_hora_limite():
    m = with_or(flat())
    bar5(m, 22, 109, 112.5, 108.5, 112)       # 11:20 ruptura
    bar5(m, 23, 111, 112.5, 110.0, 112)       # 11:25 retesteo → señal a las 11:30 (minuto 120): permitido
    assert detect(m, 390, ST)[1] == "senal"
    m = with_or(flat())
    bar5(m, 23, 109, 112.5, 108.5, 112)
    bar5(m, 24, 111, 112.5, 110.0, 112)       # señal a las 11:35: no
    assert detect(m, 390, ST)[0] is None


def test_contratos():
    # R 4 pts → (4 + 2 ticks de deslizamiento) × 2 $ + 2 $ de comisión = 11 $ por contrato
    assert contracts_for(50, 4.0, C, 50) == 4
    assert contracts_for(5, 4.0, C, 50) == 0
    assert contracts_for(10_000, 1.0, C, 50) == 50


def _session(m, d="2024-03-11", close_min=390):
    return Session(pd.Timestamp(d), m, close_min, 1, False)


def test_una_operacion_por_sesion():
    m = long_setup()
    bar5(m, 10, 112, 125, 112, 125)           # segundo impulso (no debe abrir otra)
    t, days = run([_session(m)], BASELINE)
    assert len(t) == 1 and (days.motivo == "operacion").sum() == 1


def test_sin_lookahead():
    """Cambiar todo lo posterior al minuto de señal no cambia la señal ni el minuto/precio de entrada."""
    m = long_setup()
    sig, _ = detect(m, 390, ST)
    tr, _ = simulate(sig, m, 390, ST, C)
    rng = np.random.default_rng(0)
    m2 = m.copy()
    m2[sig.signal_k + 1:, :4] = 112 + rng.normal(0, 3, (390 - sig.signal_k - 1, 1)).round() * T
    m2[:, 1] = np.maximum(m2[:, 1], m2[:, [0, 3]].max(axis=1))
    m2[:, 2] = np.minimum(m2[:, 2], m2[:, [0, 3]].min(axis=1))
    sig2, _ = detect(m2, 390, ST)
    tr2, _ = simulate(sig2, m2, 390, ST, C)
    assert (sig2.side, sig2.signal_k, sig2.retest_low) == (sig.side, sig.signal_k, sig.retest_low)
    assert (tr2.entry_k, tr2.entry, tr2.sl) == (tr.entry_k, tr.entry, tr.sl)


def test_media_jornada_cierra_antes():
    m = long_setup()
    t, _ = run([_session(m, close_min=210)], BASELINE)
    assert t.iloc[0].reason == "tiempo" and t.iloc[0].exit_k == 205


def test_sesion_corta_se_excluye():
    _, days = run([_session(long_setup(), close_min=100)], BASELINE)
    assert days.iloc[0].motivo == "sesion_demasiado_corta"


def test_limite_de_drawdown_detiene_entradas():
    m = long_setup()
    m[30, 0] = m[30, 1] = m[30, 2] = m[30, 3] = 105.0     # pérdida (hueco)
    S = [_session(m.copy(), d) for d in ("2024-03-11", "2024-03-12", "2024-03-13")]
    t, _ = run(S, BASELINE)
    cfg = Config(risk=Risk(risk_usd=100, max_drawdown=50))
    z = size_and_account(t, cfg)
    assert z.iloc[0].contracts > 0 and (z.iloc[1:].skipped == "limite_drawdown_alcanzado").all()


def test_reproducible():
    S = [_session(long_setup(), d) for d in ("2024-03-11", "2024-03-12")]
    a, _ = run(S, BASELINE)
    b, _ = run(S, BASELINE)
    pd.testing.assert_frame_equal(a, b)


def test_horario_de_verano():
    """9:30 ET es 14:30 UTC en invierno y 13:30 UTC en verano (EE. UU. cambió el 10-mar-2024)."""
    utc = pd.DatetimeIndex(["2024-03-08 14:30", "2024-03-11 13:30"], tz="UTC").tz_convert("America/New_York")
    assert all((t.hour, t.minute) == (9, 30) for t in utc)


def test_sesiones_reales_empiezan_a_las_930():
    """En los datos reales, el minuto 0 de cada sesión corresponde a 9:30 ET en ambos horarios."""
    from data.loaders import nq_1m
    df = nq_1m()
    for d in ("2024-03-08", "2024-03-11", "2024-11-01", "2024-11-04"):
        x = df.loc[d]
        assert x.index[(x.index.hour == 9) & (x.index.minute == 30)].size == 1
