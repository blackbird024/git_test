"""Pruebas del London Range Breakout: horas (invierno/verano), ruptura por cierre, 1 operación/día, SL/TP."""
import datetime as dt

import pandas as pd
import pytest

from src.strategies.london_range_breakout import Config, operar_dia


def dia(fecha: str, filas_despues: dict, base=2000.0):
    """Rango 08:00-08:59 de Londres entre 1995 y 2005; después, precio plano en 2000 salvo `filas_despues`
    (claves = hora de Londres 'HH:MM')."""
    ini = pd.Timestamp(f"{fecha} 07:00", tz="Europe/London")
    idx = pd.date_range(ini, periods=600, freq="1min").tz_convert("UTC")
    df = pd.DataFrame({"open": base, "high": base + 1, "low": base - 1, "close": base}, index=idx)
    loc = df.index.tz_convert("Europe/London")
    df.loc[(loc.hour == 8) & (loc.minute == 10), "high"] = 2005.0
    df.loc[(loc.hour == 8) & (loc.minute == 20), "low"] = 1995.0
    for hhmm, fila in filas_despues.items():
        t = pd.Timestamp(f"{fecha} {hhmm}", tz="Europe/London").tz_convert("UTC")
        df.loc[t, ["open", "high", "low", "close"]] = fila
    df["volume"] = 1.0
    return df


RUPTURA = {"09:30": (2004.0, 2006.0, 2003.0, 2005.5),     # cierra por encima de 2005 -> señal
           "09:31": (2005.6, 2006.0, 2005.0, 2005.8)}     # entrada en su apertura: 2005,6 + 1 tick


def test_winter_and_summer_range_in_utc():
    # 15-ene (GMT): el rango son las 08:00-08:59 UTC. 15-jul (BST): 07:00-07:59 UTC.
    for fecha, hora_utc in (("2024-01-15", "09:31"), ("2024-07-15", "08:31")):
        motivo, op = operar_dia(dt.date.fromisoformat(fecha), dia(fecha, RUPTURA), Config())
        assert motivo == "operada"
        assert op.t_entrada == pd.Timestamp(f"{fecha} {hora_utc}", tz="UTC")


def test_long_breakout_levels_and_2r():
    motivo, op = operar_dia(dt.date(2024, 1, 15), dia("2024-01-15", RUPTURA), Config())
    assert op.direccion == 1 and op.entrada == pytest.approx(2005.7)
    assert op.stop == 1995.0                                     # otro extremo del rango
    assert op.objetivo == pytest.approx(2005.7 + 2 * 10.7)       # 2R
    assert op.motivo == "tiempo"                                 # el precio no llega ni al stop ni al objetivo
    assert op.t_salida == pd.Timestamp("2024-01-15 16:30", tz="UTC")


def test_wick_outside_range_is_not_a_breakout():
    mecha = {"09:30": (2004.0, 2010.0, 2003.0, 2004.5)}          # la mecha sale, el cierre no
    assert operar_dia(dt.date(2024, 1, 15), dia("2024-01-15", mecha), Config())[0] == "sin_ruptura"


def test_only_first_breakout_of_the_day():
    doble = {**RUPTURA, "10:00": (1996.0, 1996.0, 1990.0, 1990.5)}   # después rompe abajo: se ignora
    motivo, op = operar_dia(dt.date(2024, 1, 15), dia("2024-01-15", doble), Config())
    assert op.direccion == 1 and op.motivo == "stop"                 # la caída posterior le saca por el stop


def test_short_hits_target():
    corto = {"09:30": (1996.0, 1997.0, 1994.0, 1994.5), "09:31": (1994.4, 1994.5, 1994.0, 1994.2),
             "09:40": (1994.0, 1994.0, 1965.0, 1970.0)}
    motivo, op = operar_dia(dt.date(2024, 1, 15), dia("2024-01-15", corto), Config())
    assert op.direccion == -1 and op.entrada == pytest.approx(1994.3) and op.stop == 2005.0
    assert op.motivo == "objetivo" and op.salida == pytest.approx(1994.3 - 2 * 10.7)
