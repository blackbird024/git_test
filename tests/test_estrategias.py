"""Pruebas de las tres ventajas del paso 1 con datos inventados (calculadas a mano)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategies import barrido_londres as bl
from src.strategies import nq_rsi2, oro_fin_de_semana


# ---------------------------------------------------------------------------- barrido de Londres
def dia_oro(barras_ventana: dict, ventana2: dict | None = None):
    """Sesión anterior (15-ene) con máximo 2003 y mínimo 1990; el 16-ene Asia plana (2001 / 1999).
    Enero: Italia = UTC+1, así que las 08:50 de Italia son las 07:50 UTC."""
    prev = pd.date_range("2024-01-15 14:00", "2024-01-15 21:59", freq="1min", tz="UTC")
    p = pd.DataFrame({"open": 1995.0, "high": 1995.5, "low": 1994.5, "close": 1995.0}, index=prev)
    p.iloc[10, 1], p.iloc[20, 2] = 2003.0, 1990.0
    hoy = pd.date_range("2024-01-15 23:00", "2024-01-16 11:00", freq="1min", tz="UTC")
    d = pd.DataFrame({"open": 2000.0, "high": 2001.0, "low": 1999.0, "close": 2000.0}, index=hoy)
    tras = d.index >= pd.Timestamp("2024-01-16 07:50", tz="UTC")
    d.loc[tras, ["open", "high", "low", "close"]] = [2000.0, 2000.5, 1999.5, 2000.0]
    for hhmm, fila in {**barras_ventana, **(ventana2 or {})}.items():
        d.loc[pd.Timestamp(f"2024-01-16 {hhmm}", tz="UTC"), ["open", "high", "low", "close"]] = fila
    m1 = pd.concat([p, d])
    m1["volume"] = 10.0
    return m1


BARRIDO = {"07:50": (2000.0, 2001.5, 1999.8, 2001.2),
           "07:51": (2001.2, 2002.0, 2001.0, 2001.8),
           "07:52": (2001.8, 2003.5, 2002.2, 2002.8),   # supera el máximo anterior (2003) y cierra dentro; FVG
           "07:53": (2002.8, 2002.9, 2001.6, 2001.8),
           "07:54": (2001.8, 2001.9, 2001.0, 2001.2),   # cierra bajo el FVG (2001,5) -> IFVG
           "07:55": (2001.2, 2001.3, 2000.5, 2000.6),   # entrada (08:55 Italia, apertura de Londres: 2 ticks)
           "07:56": (2000.6, 2000.7, 1992.9, 1993.0)}   # objetivo


def test_london_sweep_ifvg_short():
    ops = bl.backtest(dia_oro(BARRIDO), bl.Config())
    op = ops.iloc[0]
    assert op.direccion == -1 and op.motivo == "objetivo|IFVG"
    assert op.t_entrada == pd.Timestamp("2024-01-16 07:55", tz="UTC")
    assert op.entrada == pytest.approx(2001.0)                  # 2001,2 - 2 ticks
    assert op.stop == pytest.approx(2005.0)                     # 2003,5 + 1,5
    assert op.contratos == 6                                    # floor(250 / (4 x 10))
    assert op.objetivo == pytest.approx(1993.0)                 # 2R
    assert op.neto == pytest.approx(8.0 * 10 * 6 - 12)


def test_level_already_taken_before_window_does_not_count():
    # A las 08:20 UTC (09:20 Italia, fuera de ventana) el precio ya supera el máximo de Asia y el anterior.
    antes = {"08:20": (2000.0, 2004.0, 2000.0, 2000.0)}
    v2 = {"09:05": (2000.0, 2004.5, 1999.8, 2000.2), "09:06": (2000.2, 2000.3, 1995.0, 1995.5)}
    ops = bl.backtest(dia_oro({**antes, **v2}), bl.Config())
    assert ops.empty


def test_loss_ends_the_day():
    perdida = dict(BARRIDO)
    perdida["07:56"] = (2000.6, 2006.0, 2000.5, 2005.5)          # sube al stop
    segundo = {"09:10": (2000.0, 2000.2, 1989.0, 1990.5), "09:11": (1990.5, 1990.6, 1988.0, 1988.2)}
    ops = bl.backtest(dia_oro(perdida, segundo), bl.Config())
    assert len(ops) == 1 and ops.iloc[0].motivo.startswith("stop")


# ------------------------------------------------------------------------------ fin de semana
def sesion(fecha_ny_cierre: str, abre: float, cierra: float, contrato=1):
    """Una sesión corta: 18:00 NY del día anterior a 17:00 NY. Solo 3 velas (apertura, medio, cierre)."""
    fin = pd.Timestamp(f"{fecha_ny_cierre} 16:59", tz="America/New_York").tz_convert("UTC")
    ini = (pd.Timestamp(f"{fecha_ny_cierre} 16:59", tz="America/New_York") - pd.Timedelta(hours=22, minutes=59)).tz_convert("UTC")
    idx = pd.DatetimeIndex([ini, ini + pd.Timedelta(hours=10), fin])
    return pd.DataFrame({"open": [abre, abre, cierra], "high": max(abre, cierra), "low": min(abre, cierra),
                         "close": [abre, abre, cierra], "volume": 1.0, "instrument_id": contrato}, index=idx)


def test_friday_to_monday_trade():
    dias = pd.bdate_range("2024-01-01", "2024-02-09")
    precios = 2000 + np.arange(len(dias)) * 1.0
    m1 = pd.concat([sesion(str(d.date()), p, p) for d, p in zip(dias, precios)])
    ops = oro_fin_de_semana.backtest(m1)
    viernes = ops[ops.dia_entrada == "viernes"]
    assert len(viernes) == len(ops) > 0                          # solo pares de fin de semana
    # compra 1 tick por encima, venta 1 tick por debajo, +1 $ de precio -> (1 - 0,2) x 10 - 2 = 6 $
    assert viernes.neto.iloc[0] == pytest.approx((1.0 - 0.2) * 10 - 2.0)


# ---------------------------------------------------------------------------------------- RSI(2)
def test_rsi_wilder_basic():
    s = pd.Series([1, 2, 3, 2, 1, 2, 3, 4], dtype=float)
    r = nq_rsi2.rsi(s, 2)
    # Subidas +1, +1 y bajadas -1, -1 con suavizado de Wilder (alfa 1/2): media de subidas 0,25 y de bajadas 0,75.
    assert np.isnan(r.iloc[0]) and r.iloc[2] == 100 and r.iloc[4] == pytest.approx(25.0)


def test_rsi2_entry_next_open_and_time_exit():
    dias = pd.bdate_range("2023-01-02", periods=260)
    precios = list(np.linspace(100, 200, 250)) + [190, 185, 186, 187, 188, 189, 190, 191, 192, 193]
    m1 = pd.concat([sesion(str(d.date()), p, p) for d, p in zip(dias, precios)])
    ops = nq_rsi2.backtest(m1, nq_rsi2.Config(salida=101))       # sin salida por RSI: solo por tiempo
    op = ops.iloc[0]
    senal = pd.Timestamp(f"{dias[250].date()} 16:59", tz="America/New_York").tz_convert("UTC")
    assert op.t_senal == senal and op.t_entrada > op.t_senal     # entra en la apertura de la sesión siguiente
    assert op.sesiones == 5 and op.motivo == "tiempo"
