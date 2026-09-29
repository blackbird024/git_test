"""Pruebas de OR_VWAP_v1.0: rango, VWAP, rupturas, stop, objetivo, tamaño, límite diario, salida por tiempo,
horario de verano, tope de 40 puntos y look-ahead."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.risk.position_sizing import contratos
from src.strategies.mnq_or_vwap import Config, backtest, operar_dia, senal, vwap_sesion

TZ = "America/New_York"


def sesion(fecha: str, cambios: dict, base=100.0):
    """Sesión regular de 1M (09:30-15:59 NY) plana en `base`, rango 09:30-09:44 entre 95 y 105."""
    idx = pd.date_range(pd.Timestamp(f"{fecha} 09:30", tz=TZ), periods=390, freq="1min").tz_convert("UTC")
    df = pd.DataFrame({"open": base, "high": base + 0.5, "low": base - 0.5, "close": base, "volume": 10.0}, index=idx)
    loc = idx.tz_convert(TZ)
    df.loc[(loc.hour == 9) & (loc.minute == 35), "high"] = 105.0
    df.loc[(loc.hour == 9) & (loc.minute == 40), "low"] = 95.0
    for hhmm, fila in cambios.items():
        t = pd.Timestamp(f"{fecha} {hhmm}", tz=TZ).tz_convert("UTC")
        df.loc[t, ["open", "high", "low", "close"]] = fila
    return df


LARGO = {"10:00": (104.0, 106.0, 104.0, 105.5), "10:01": (105.5, 106.0, 105.0, 105.75)}
F = dt.date(2024, 1, 16)


def test_opening_range_frozen_and_vwap():
    df = sesion("2024-01-16", {**LARGO, "11:00": (110, 130, 70, 100)})      # vela enorme después: no cambia el rango
    s = senal(df, F, Config())
    assert (s["or_high"], s["or_low"]) == (105.0, 95.0)
    v = vwap_sesion(df.iloc[:2])
    tip = (df.high + df.low + df.close) / 3
    assert v.iloc[1] == pytest.approx((tip.iloc[0] * 10 + tip.iloc[1] * 10) / 20)


def test_long_breakout_entry_stop_target():
    estado, op, s = operar_dia(sesion("2024-01-16", LARGO), F, 50_000, Config())
    assert estado == "operada" and op.direccion == 1
    assert op.t_senal == pd.Timestamp("2024-01-16 10:00", tz=TZ) and op.t_entrada == pd.Timestamp("2024-01-16 10:01", tz=TZ)
    assert op.entrada == 105.75 and op.stop == 95.0                     # apertura siguiente + 1 tick; stop = OR_low
    r = 105.75 - 95.0
    assert op.objetivo == pytest.approx(105.75 + 2 * r)
    assert op.contratos == contratos(50_000, 0.005, r, 2.0) == 11       # floor(250 / 21,5)


def test_short_breakout_and_vwap_filter():
    corto = {"10:00": (96.0, 96.0, 94.0, 94.5), "10:01": (94.5, 95.0, 94.0, 94.25)}
    estado, op, _ = operar_dia(sesion("2024-01-16", corto), F, 50_000, Config())
    assert estado == "operada" and op.direccion == -1 and op.stop == 105.0 and op.entrada == 94.25
    # Ruptura al alza (cierre 105,5 > OR_high 105) pero con el cierre por debajo del VWAP: no es señal.
    df = sesion("2024-01-16", {"10:00": (104.0, 106.0, 104.0, 105.5)})
    t946 = pd.Timestamp("2024-01-16 09:46", tz=TZ).tz_convert("UTC")
    df.loc[t946, ["open", "high", "low", "close", "volume"]] = (104.0, 140.0, 104.0, 104.5, 1000.0)  # no rompe (cierre 104,5)
    vw = vwap_sesion(df).loc[pd.Timestamp("2024-01-16 10:00", tz=TZ).tz_convert("UTC")]
    assert vw > 105.5                                                    # el VWAP queda por encima del cierre de ruptura
    assert senal(df, F, Config())["estado"] == "sin_senal"


def test_touch_is_not_breakout_and_one_trade_per_day():
    toque = {"10:00": (104.0, 105.5, 104.0, 105.0)}                     # la mecha supera 105, el cierre no
    assert senal(sesion("2024-01-16", toque), F, Config())["estado"] == "sin_senal"
    dos = {**LARGO, "10:30": (95.0, 95.0, 90.0, 90.5)}                  # después rompe abajo
    ops, estados = backtest(sesion("2024-01-16", dos), Config())
    assert len(ops) == 1 and ops.iloc[0].direccion == 1 and ops.iloc[0].motivo == "stop"


def test_target_and_time_exit():
    objetivo = {**LARGO, "10:30": (106, 130, 106, 128)}
    op = operar_dia(sesion("2024-01-16", objetivo), F, 50_000, Config())[1]
    assert op.motivo == "objetivo" and op.salida == pytest.approx(105.75 + 2 * 10.75)
    op = operar_dia(sesion("2024-01-16", LARGO), F, 50_000, Config())[1]
    assert op.motivo == "tiempo" and op.t_salida == pd.Timestamp("2024-01-16 15:55", tz=TZ)


def test_risk_cap_and_zero_contracts():
    ancho = sesion("2024-01-16", LARGO)
    loc = ancho.index.tz_convert(TZ)
    ancho.loc[(loc.hour == 9) & (loc.minute == 40), "low"] = 50.0      # R = 55,75 > 40
    assert operar_dia(ancho, F, 50_000, Config())[0] == "riesgo_mayor_que_tope"
    assert operar_dia(sesion("2024-01-16", LARGO), F, 1_000, Config())[0] == "cero_contratos"   # 5 $ / 21,5 $ < 1
    assert contratos(50_000, 0.005, 0, 2.0) == 0 and contratos(-1, 0.005, 10, 2.0) == 0


def test_dst_winter_and_summer():
    # 09:30 NY = 14:30 UTC en enero y 13:30 UTC en julio; en la semana de desajuste (15-mar) ya es 13:30 UTC.
    for fecha, hora_utc in (("2024-01-16", "15:00"), ("2024-07-16", "14:00"), ("2024-03-15", "14:00")):
        s = senal(sesion(fecha, LARGO), dt.date.fromisoformat(fecha), Config())
        assert s["t_senal"] == pd.Timestamp(f"{fecha} {hora_utc}", tz="UTC")


def test_no_duplicates_needed_and_signal_uses_only_closed_bars():
    df = sesion("2024-01-16", LARGO)
    futuro = df.copy()
    futuro.iloc[200:] = futuro.iloc[200:] * 3                           # cambiar el futuro no cambia la señal
    assert senal(df, F, Config())["t_senal"] == senal(futuro, F, Config())["t_senal"]
