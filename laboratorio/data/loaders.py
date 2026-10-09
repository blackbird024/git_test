"""Carga de datos del laboratorio. Solo lectura de los archivos originales.

NQ 1 min (Databento GLBX.MDP3, ohlcv-1m, contrato continuo NQ.c.0) en dos archivos de alpaca/.lab_cache:
  databento_nq_1m_2018_2024.pkl  (2018-01-01 → 2024-09-30)
  databento_glbx_1m.pkl          (2024-10-01 → 2026-10-02; contiene NQ, ES, GC: se filtra NQ)
Auditoría completa en orb_mnq/reports/auditoria_datos.json.

Sesiones: calendario XNYS (exchange_calendars). Cada sesión se representa con una matriz de 390 minutos
(9:30-15:59 ET) con NaN donde no hubo operaciones; las medias jornadas acaban antes (close_min < 390).
"""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "alpaca" / ".lab_cache"
CACHE = Path(__file__).resolve().parent / "cache"
ET = "America/New_York"
ROME = "Europe/Rome"
TICK = 0.25


@lru_cache(maxsize=1)
def nq_1m() -> pd.DataFrame:
    """NQ 1 min unido, índice en America/New_York, columnas OHLCV + instrument_id."""
    cache = CACHE / "nq_1m_et.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    a = pd.read_pickle(SRC / "databento_nq_1m_2018_2024.pkl")
    b = pd.read_pickle(SRC / "databento_glbx_1m.pkl")
    b = b[b["symbol"] == "NQ.c.0"]
    cols = ["open", "high", "low", "close", "volume", "instrument_id"]
    df = pd.concat([a[cols], b[cols]]).sort_index()
    assert not df.index.duplicated().any(), "timestamps duplicados al unir los archivos"
    df.index = df.index.tz_convert(ET)
    CACHE.mkdir(exist_ok=True)
    df.to_pickle(cache)
    return df


@dataclass
class Session:
    date: pd.Timestamp
    m: np.ndarray            # (390, 5) open, high, low, close, volume; NaN si no hubo operaciones
    close_min: int           # minutos de sesión (390 normal, 210 media jornada)
    instrument_id: int
    roll_week: bool          # semana del vencimiento trimestral (el continuo sigue en el contrato que vence)
    globex_open: float = np.nan   # apertura de la sesión Globex (18:00 ET del día anterior)
    extra: dict = field(default_factory=dict)


def _roll_weeks(df: pd.DataFrame) -> set:
    """Fechas (lunes-viernes) de la semana anterior a cada cambio de instrument_id."""
    ids = df["instrument_id"]
    chg = ids.index[ids.ne(ids.shift())][1:]
    out = set()
    for t in chg:
        d = t.normalize().tz_localize(None)
        for k in range(1, 9):
            x = d - pd.Timedelta(days=k)
            if x.weekday() < 5:
                out.add(x.date())
    return out


@lru_cache(maxsize=1)
def sessions() -> list:
    """Lista de Session para cada sesión XNYS con datos."""
    cache = CACHE / "sessions.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    import exchange_calendars as xc
    cal = xc.get_calendar("XNYS")
    df = nq_1m()
    sch = cal.schedule.loc[str(df.index[0].date()):str(df.index[-1].date())]
    rolls = _roll_weeks(df)
    t = df.index
    mins = (t.hour * 60 + t.minute).to_numpy()
    dates = t.date
    arr = df[["open", "high", "low", "close", "volume"]].to_numpy()
    ins = df["instrument_id"].to_numpy()
    # índice por fecha
    order = pd.Series(np.arange(len(df)), index=pd.Index(dates)).groupby(level=0).agg(["min", "max"])
    out = []
    for d, row in sch.iterrows():
        dd = d.date()
        if dd not in order.index:
            continue
        lo, hi = order.loc[dd, "min"], order.loc[dd, "max"] + 1
        mm = mins[lo:hi] - 570
        close_min = int((row["close"] - row["open"]).total_seconds() // 60)
        sel = (mm >= 0) & (mm < close_min)
        if sel.sum() < 30:
            continue
        m = np.full((390, 5), np.nan)
        m[mm[sel]] = arr[lo:hi][sel]
        # apertura Globex: primera vela desde las 18:00 ET del día hábil anterior
        g = np.nan
        prev_lo = order.index.searchsorted(dd) - 1
        if prev_lo >= 0:
            pd_ = order.index[prev_lo]
            plo, phi = order.loc[pd_, "min"], order.loc[pd_, "max"] + 1
            pm = mins[plo:phi]
            k = np.nonzero(pm >= 18 * 60)[0]
            if len(k):
                g = arr[plo + k[0], 0]
        out.append(Session(pd.Timestamp(dd), m, close_min, int(ins[lo:hi][sel][0]), dd in rolls, g))
    CACHE.mkdir(exist_ok=True)
    pd.to_pickle(out, cache)
    return out


def daily_from_sessions(S: list) -> pd.DataFrame:
    """OHLC de la sesión regular (9:30-16:00 ET) de NQ, una fila por sesión."""
    rows = []
    for s in S:
        x = s.m[: s.close_min]
        ok = ~np.isnan(x[:, 0])
        x = x[ok]
        rows.append((s.date, x[0, 0], x[:, 1].max(), x[:, 2].min(), x[-1, 3], np.nansum(x[:, 4]), s.roll_week))
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "roll_week"]).set_index("date")


def bars5(s: Session) -> np.ndarray:
    """Velas de 5 min (78 como máximo) alineadas a 9:30, construidas desde las de 1 min. NaN si el bloque está vacío."""
    n = s.close_min // 5
    out = np.full((n, 4), np.nan)
    for k in range(n):
        x = s.m[5 * k: 5 * k + 5]
        ok = ~np.isnan(x[:, 0])
        if ok.any():
            y = x[ok]
            out[k] = (y[0, 0], y[:, 1].max(), y[:, 2].min(), y[-1, 3])
    return out


def etf_daily(symbol="QQQ", adjusted=True, last=None) -> pd.DataFrame:
    df = pd.read_pickle(CACHE / f"{symbol}_daily_{'adj' if adjusted else 'raw'}.pkl")
    df.index = pd.to_datetime(df.index)
    if last is not None:
        df = df[df.index <= pd.Timestamp(last)]
    return df


def et_to_rome(date, hhmm: str) -> str:
    """Hora de Nueva York → hora de Italia para una fecha concreta (gestiona los dos cambios de horario)."""
    t = pd.Timestamp(f"{pd.Timestamp(date).date()} {hhmm}").tz_localize(ET).tz_convert(ROME)
    return t.strftime("%H:%M")
