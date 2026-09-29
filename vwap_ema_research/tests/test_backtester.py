import numpy as np
import pandas as pd
import pytest

from src.backtester import run
from src.data_loader import build
from src.strategy import features


def _run(cfg, inst, p, precios, **cambios):
    p = dict(p, sizing="fixed", **cambios)
    ses = build(__import__("tests.conftest", fromlist=["sesion"]).sesion("2024-06-03", precios), inst, cfg["general"])
    x = features(ses.bars, p)
    x["atr"] = 2.0
    return run(x, ses.sub, p, inst, 50_000)


def _subida_bajada():
    p = np.full(390, 100.0)
    p[15:] = 95.0                                  # vela 0 = 100 (VWAP 100), vela 1 en adelante 95: por debajo del VWAP
    return p


def test_entrada_en_apertura_siguiente_y_fin_de_sesion(cfg, inst, p):
    t = _run(cfg, inst, p, _subida_bajada()).trades
    op = t.iloc[0]
    assert op.direction == -1
    hora = pd.Timestamp(op.entry_time).tz_localize("UTC").tz_convert("America/New_York").strftime("%H:%M")
    assert hora == "10:00"                          # señal al cierre de la vela 09:45, entrada a las 10:00
    assert op.entry_price == 94.75 and op.exit_reason == "fin_de_sesion"
    assert op.net_pnl == pytest.approx(-(95.25 - 94.75) * 2 - 1.7)


def test_stop_y_salida_temporal(cfg, inst, p):
    pr = _subida_bajada()
    pr[40] = 100.0                                  # vela de 10:15: sube por encima del stop 94,75 + 3 = 97,75
    op = _run(cfg, inst, p, pr).trades.iloc[0]
    assert op.exit_reason == "stop" and op.raw_entry == 95
    op = _run(cfg, inst, p, _subida_bajada(), exit_type="time", time_exit_minutes=30).trades.iloc[0]
    assert op.exit_reason == "tiempo" and op.minutes == 30


def test_parcial_y_breakeven(cfg, inst, p):
    pr = _subida_bajada()
    pr[45:60] = 91.0                                # 1R = 3 puntos -> parcial en 91,75
    pr[60:] = 95.0                                  # vuelve a la entrada: stop en breakeven
    op = _run(cfg, inst, p, pr, exit_type="partial_trailing", fixed_contracts=2).trades.iloc[0]
    assert op.partial and op.exit_reason == "trailing_o_breakeven"
    assert op.gross_pnl == pytest.approx((95 - 91.75) * 2 * 1 + (95 - 94.75) * 2 * 1, abs=1.0)
