"""Sesiones, calendario y velas horarias.

- Todo en America/New_York (zona IANA): el cambio de horario lo gestiona tzdata; no hay desplazamientos UTC fijos.
- Sesión regular: velas de 5 min cuya APERTURA está en [session_start, session_end).
- Calendario: si `exchange_calendars` está instalado se usa el calendario XNYS para excluir festivos (en los que Globex
  puede abrir con horario reducido) y detectar cierres anticipados (13:00 ET). Sin él, la sesión se deduce de los datos
  y se avisa.
- Velas de 1 h: rejilla de horas en punto de Nueva York (…, 8:00-9:00, 9:00-10:00, …) construidas con TODAS las velas de
  5 min disponibles (incluida la sesión nocturna de Globex). Nunca cruzan la pausa diaria 17:00-18:00 ET porque no hay
  datos en ella. Una vela de 1 h solo existe cuando tiene al menos `hourly_min_bars` velas de 5 min (de 12) y solo es
  utilizable a partir de su hora de cierre (inicio + 60 min).
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class SessionBars:
    date: pd.Timestamp
    start: pd.DatetimeIndex      # apertura de cada vela (ET)
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    flat_time: time
    early_close: bool = False
    contract: Optional[str] = None
    invalid_reason: Optional[str] = None


def _calendar(first, last):
    try:
        import exchange_calendars as xc
    except ImportError:
        return None
    cal = xc.get_calendar("XNYS")
    lo = max(pd.Timestamp(first.date()), cal.first_session)
    hi = min(pd.Timestamp(last.date()), cal.last_session)
    return cal.schedule.loc[lo:hi]


def sessions(df: pd.DataFrame, strat, bar_minutes: int):
    """Divide los datos en sesiones regulares. Devuelve (lista de SessionBars, aviso_calendario)."""
    t = df.index
    tod = t.hour * 60 + t.minute
    a = strat.session_start.hour * 60 + strat.session_start.minute
    b = strat.session_end.hour * 60 + strat.session_end.minute
    rth = (tod >= a) & (tod < b) & (t.dayofweek < 5)
    x = df[rth]
    sch = _calendar(t[0], t[-1])
    warn = None if sch is not None else "exchange_calendars no instalado: festivos y cierres anticipados deducidos de los datos"
    out = []
    has_contract = "contract" in x.columns
    for d, g in x.groupby(x.index.date):
        day = pd.Timestamp(d)
        flat = strat.flat_time
        early = False
        reason = None
        if sch is not None:
            if day not in sch.index:
                reason = "festivo NYSE (sin sesión regular)"
            else:
                close_et = sch.loc[day, "close"].tz_convert(t.tz)
                if close_et.time() < strat.session_end:
                    early = True
                    lim = (close_et - pd.Timedelta(minutes=bar_minutes)).time()
                    flat = min(flat, lim)
                    g = g[g.index < close_et]
        out.append(SessionBars(day, g.index, g["open"].to_numpy(), g["high"].to_numpy(),
                               g["low"].to_numpy(), g["close"].to_numpy(), flat, early,
                               str(g["contract"].iloc[0]) if has_contract and len(g) else None, reason))
    return out, warn


@dataclass
class Hourly:
    start: pd.DatetimeIndex
    close_time: pd.DatetimeIndex
    h: np.ndarray
    l: np.ndarray
    n_bars: np.ndarray
    dropped: int = 0


def hourly_bars(df: pd.DataFrame, min_bars: int) -> Hourly:
    key = df.index.floor("h")
    g = df.groupby(key)
    agg = pd.DataFrame({"h": g["high"].max(), "l": g["low"].min(), "n": g["high"].size()})
    keep = agg["n"] >= min_bars
    agg2 = agg[keep]
    st = pd.DatetimeIndex(agg2.index)
    return Hourly(st, st + pd.Timedelta(hours=1), agg2["h"].to_numpy(), agg2["l"].to_numpy(), agg2["n"].to_numpy(),
                  dropped=int((~keep).sum()))
