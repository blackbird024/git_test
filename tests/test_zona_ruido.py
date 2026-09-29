"""Pruebas de ZONA_RUIDO_MNQ_v1.0 (portadas de archive/tests/test_noise_area.py).

Día inventado con sigma fija del 1 %: apertura 100 y cierre anterior 100 -> banda superior 101, inferior 99.
MNQ, 1 contrato: 1 punto = 2 $, tick 0,25, comisión 1 $ por lado.
"""
import datetime as dt

import numpy as np
import pandas as pd

from src.strategies.zona_ruido import Config, operar_dia

D = "2024-03-04"
FECHA = dt.date(2024, 3, 4)
TZ = "America/New_York"
CFG = Config()
SIGMA = pd.Series(0.01, index=range(390))


def dia(precios: dict, base=100.0):
    close = np.full(390, base)
    for m in sorted(precios):
        close[m:] = precios[m]
    idx = pd.date_range(f"{D} 09:30", periods=390, freq="1min", tz=TZ)
    df = pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close}, index=idx)
    df["volume"] = 1.0
    df["minute"] = range(390)
    return df


def test_long_breakout_held_until_close():
    t, = operar_dia(FECHA, dia({20: 102.0}), 100.0, 100.0, SIGMA, CFG)
    assert t["direccion"] == 1
    assert t["t_entrada"] == pd.Timestamp(f"{D} 10:00", tz=TZ)          # primer chequeo, nunca antes
    assert t["entrada"] == 102.25 and t["motivo"] == "cierre" and t["salida"] == 101.75


def test_no_trade_inside_noise_area():
    assert operar_dia(FECHA, dia({20: 100.5, 200: 99.5}), 100.0, 100.0, SIGMA, CFG) == []


def test_decision_only_at_half_hours_with_previous_close():
    # Sale de la zona a las 10:01 y vuelve a las 10:20: en el chequeo de 10:30 ya está dentro -> sin operación
    assert operar_dia(FECHA, dia({31: 102.0, 50: 100.0}), 100.0, 100.0, SIGMA, CFG) == []
    # El precio del minuto del chequeo (10:00) no se usa para decidir: decide el cierre de 09:59
    assert operar_dia(FECHA, dia({30: 102.0, 31: 100.0}), 100.0, 100.0, SIGMA, CFG) == []


def test_trailing_exit_and_flip_at_check():
    t1, t2 = operar_dia(FECHA, dia({20: 102.0, 70: 98.0}), 100.0, 100.0, SIGMA, CFG)
    assert t1["direccion"] == 1 and t1["motivo"] == "trailing"
    assert t1["t_salida"] == pd.Timestamp(f"{D} 11:00", tz=TZ) and t1["salida"] == 97.75
    assert t2["direccion"] == -1 and t2["t_entrada"] == pd.Timestamp(f"{D} 11:00", tz=TZ) and t2["entrada"] == 97.75


def test_gap_anchor_uses_previous_close():
    # Cierre anterior 103 y apertura 100: la banda superior se ancla en 103 -> 104,03; 103 no basta para comprar
    assert operar_dia(FECHA, dia({20: 103.0}), 100.0, 103.0, SIGMA, CFG) == []
