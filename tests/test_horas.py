"""Conversión de horas: MT5 -> UTC -> Italia, incluidas las semanas en que el horario de verano de
EE. UU. y de Europa no coincide (en 2024: del 10 al 31 de marzo y del 27 de octubre al 3 de noviembre)."""
import pandas as pd

from src.data.cargadores import servidor_a_utc
from src.horas import ROMA, en_ventana, hora_local_a_utc, sesion_cme


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_mt5_server_us_rule():
    horas = pd.Series(pd.to_datetime(["2024-01-15 10:00", "2024-07-15 10:00", "2024-03-15 10:00", "2024-11-01 10:00"]))
    out = servidor_a_utc(horas, "EEUU")
    assert list(out) == [utc("2024-01-15 08:00"),   # invierno: UTC+2
                         utc("2024-07-15 07:00"),   # verano: UTC+3
                         utc("2024-03-15 07:00"),   # EE. UU. ya en verano, Europa aún no -> UTC+3
                         utc("2024-11-01 07:00")]   # Europa ya en invierno, EE. UU. aún en verano -> UTC+3


def test_mt5_server_europe_rule():
    horas = pd.Series(pd.to_datetime(["2024-03-15 10:00", "2024-04-15 10:00"]))
    out = servidor_a_utc(horas, "Europa")
    assert list(out) == [utc("2024-03-15 08:00"), utc("2024-04-15 07:00")]


def test_rome_window_follows_european_dst():
    # 08:50 en Italia = 07:50 UTC en invierno y 06:50 UTC en verano.
    assert hora_local_a_utc("2024-01-15", "08:50", ROMA) == utc("2024-01-15 07:50")
    assert hora_local_a_utc("2024-07-15", "08:50", ROMA) == utc("2024-07-15 06:50")
    # 15 de marzo (desajuste): Italia sigue en invierno.
    assert hora_local_a_utc("2024-03-15", "08:50", ROMA) == utc("2024-03-15 07:50")
    idx = pd.DatetimeIndex([utc("2024-03-15 07:55"), utc("2024-07-15 07:55")])
    assert list(en_ventana(idx, "08:50", "09:10", ROMA)) == [True, False]   # en julio 07:55 UTC = 09:55 Italia


def test_cme_session_date():
    # 18:00 de Nueva York del domingo abre la sesión del lunes; durante el desajuste de marzo es 22:00 UTC.
    idx = pd.DatetimeIndex([utc("2024-03-10 21:59"), utc("2024-03-10 22:00"), utc("2024-01-14 23:00")])
    assert [str(d) for d in sesion_cme(idx)] == ["2024-03-10", "2024-03-11", "2024-01-15"]
