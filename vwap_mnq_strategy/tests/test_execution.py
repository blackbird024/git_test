import numpy as np
import pandas as pd
import pytest

from src.backtester import run
from src.execution import CostModel, check_exit_subbar
from src.session_manager import build_bars

CM = CostModel(tick=0.25, point_value=2.0, commission_per_side=0.85, slippage_ticks=1, target_requires_through=True)


def test_mercado_con_deslizamiento_en_contra():
    assert CM.market(100, 1, True) == 100.25 and CM.market(100, 1, False) == 99.75
    assert CM.market(100, -1, True) == 99.75 and CM.market(100, -1, False) == 100.25
    assert CM.commission(3) == pytest.approx(5.1)


def test_stop_y_target_en_la_misma_vela_cuenta_el_stop():
    r = check_exit_subbar(100, 105, 95, 1, stop=97, target=103, cm=CM)
    assert r[0] == "stop" and r[1] == 97 and r[2] == 96.75


def test_stop_con_hueco_se_ejecuta_en_la_apertura():
    r = check_exit_subbar(94, 95, 93, 1, stop=97, target=None, cm=CM)
    assert r[1] == 94 and r[2] == 93.75


def test_target_exige_superar_un_tick():
    assert check_exit_subbar(100, 103.0, 99.5, 1, stop=None, target=103, cm=CM) is None
    r = check_exit_subbar(100, 103.25, 99.5, 1, stop=None, target=103, cm=CM)
    assert r[0] == "target" and r[2] == 103


def _escenario(cfg, hacer_sesion, precios, **exits):
    cfg["risk"]["sizing"] = "fixed"
    cfg["strategy"]["exits"].update(exits)
    ses = build_bars(hacer_sesion("2024-06-03", precios), cfg)
    b = ses.bars.copy()
    b["vwap"], b["atr"] = b.vwap_rth, 2.0
    return run(b, ses.sub, cfg)


def _precios_base():
    p = np.full(390, 95.0)
    p[:15] = 100 + 0.1 * np.arange(15)          # vela 0 sube: cierre por encima del VWAP
    return p                                     # vela 1 en adelante: 95, por debajo -> cruce a la baja en la vela 1


def test_entrada_en_la_apertura_siguiente_y_cierre_de_sesion(cfg, hacer_sesion):
    res = _escenario(cfg, hacer_sesion, _precios_base())
    t = res.trades
    assert len(t) == 1
    op = t.iloc[0]
    assert op.direction == -1
    assert pd.Timestamp(op.entry_time).tz_localize("UTC").tz_convert("America/New_York").strftime("%H:%M") == "10:00"
    assert op.entry_price == 94.75 and op.exit_reason == "fin_de_sesion" and op.exit_price == 95.25
    assert op.net_pnl == pytest.approx(-1.0 - 1.7) and op.gross_pnl == 0


def test_stop_intravela(cfg, hacer_sesion):
    p = _precios_base()
    p[100] = 100.0                                # pico a las 11:10: supera el stop 94,75 + 2 x 2 = 98,75 con hueco
    op = _escenario(cfg, hacer_sesion, p).trades.iloc[0]
    assert op.exit_reason == "stop" and op.raw_exit == 100.0 and op.exit_price == 100.25
    assert op.r_net == pytest.approx(((94.75 - 100.25) * 2 - 1.7) / (4 * 2))


def test_target_en_r(cfg, hacer_sesion):
    p = _precios_base()
    p[120:] = 90.25                                # baja más allá del objetivo 1R = 94,75 - 4 = 90,75 (con hueco)
    op = _escenario(cfg, hacer_sesion, p, tp_r=1.0).trades.iloc[0]
    assert op.exit_reason == "target" and op.exit_price == 90.25
