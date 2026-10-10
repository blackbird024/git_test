"""Carga, control de calidad y sesiones.

Reutiliza el lector y el validador de `orb_backtest.data_io` (CSV con marca ISO 8601 con zona horaria, marca = apertura).
Añade: volumen (necesario para el VWAP), cambios de contrato y construcción de sesiones de Londres y Nueva York.

Sesión = velas de 5 min cuya apertura está en [start, flat] en la zona horaria IANA de la sesión (la vela de `flat` se
incluye solo para poder cerrar a su apertura). Las velas previas al inicio NO entran en el VWAP; sí en las EMA y el ATR,
que se calculan de forma continua sobre toda la serie de 5 min.
Sesión inválida si: festivo del calendario configurado, cobertura de velas < min_bar_coverage, volumen ausente o nulo,
cambio de contrato dentro de la sesión, o (opcional) primera sesión tras un rollover.
"""
from dataclasses import dataclass
from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from orb_backtest import data_io


def _t(s):
    h, m = s.split(":")
    return time(int(h), int(m))


@dataclass
class Session:
    name: str
    date: pd.Timestamp
    idx: np.ndarray            # posiciones en la serie global de 5 min
    start: pd.DatetimeIndex
    flat_pos: int              # posición (dentro de idx) de la vela de cierre obligatorio, -1 si no existe
    entry_end: time
    invalid: Optional[str] = None


def load(path, tick_size, bar_minutes=5):
    df = data_io.read_csv(path, "UTC")
    if "volume" not in df.columns:
        raise data_io.DataError("el VWAP necesita la columna volume")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    v = data_io.validate(df.tz_convert("America/New_York"), tick_size, bar_minutes)
    q = dict(volumen_nan=int(df["volume"].isna().sum()), volumen_cero=int((df["volume"] <= 0).sum()))
    if "contract" in df.columns:
        ch = df["contract"].astype(str)
        q["cambios_de_contrato"] = int((ch != ch.shift()).sum() - 1)
    return df, v, q


def sessions(df: pd.DataFrame, cfg_s: dict, quality: dict, bar_minutes: int = 5):
    tz = cfg_s["timezone"]
    st, ee, fl = _t(cfg_s["start"]), _t(cfg_s["entry_end"]), _t(cfg_s["flat"])
    loc = df.index.tz_convert(tz)
    tod = loc.hour * 60 + loc.minute
    a, b = st.hour * 60 + st.minute, fl.hour * 60 + fl.minute
    sel = np.nonzero((tod >= a) & (tod <= b) & (loc.dayofweek < 5))[0]
    sch = None
    if cfg_s.get("calendar"):
        import exchange_calendars as xc
        cal = xc.get_calendar(cfg_s["calendar"])
        sch = cal.schedule.loc[max(pd.Timestamp(loc[0].date()), cal.first_session):min(pd.Timestamp(loc[-1].date()), cal.last_session)]
    dates = pd.Index(loc[sel].date)
    contract = df["contract"].astype(str).to_numpy() if "contract" in df.columns else None
    vol = df["volume"].to_numpy()
    out = []
    prev_contract = None
    for d in pd.unique(dates):
        ix = sel[dates == d]
        day = pd.Timestamp(d)
        flat = fl
        reason = None
        if sch is not None:
            if day not in sch.index:
                reason = f"festivo {cfg_s['calendar']}"
            else:
                close_local = sch.loc[day, "close"].tz_convert(tz)
                if close_local.time() < _t("16:00") and close_local.time() <= fl:
                    flat = (close_local - pd.Timedelta(minutes=bar_minutes)).time()
                    keep = (loc[ix].hour * 60 + loc[ix].minute) <= flat.hour * 60 + flat.minute
                    ix = ix[keep]
        start_local = loc[ix]
        n_exp = (flat.hour * 60 + flat.minute - a) // bar_minutes + 1
        if reason is None and len(ix) < quality["min_bar_coverage"] * n_exp:
            reason = f"cobertura de velas {len(ix)}/{n_exp}"
        if reason is None and (np.isnan(vol[ix]).any() or vol[ix].sum() <= 0):
            reason = "volumen ausente o nulo"
        if contract is not None and len(ix):
            cs = set(contract[ix])
            if reason is None and len(cs) > 1:
                reason = "cambio de contrato dentro de la sesión"
            c0 = contract[ix[0]]
            if reason is None and quality.get("exclude_first_session_after_roll") and prev_contract is not None and c0 != prev_contract:
                reason = "primera sesión tras rollover (EMA/ATR afectados por el salto)"
            prev_contract = contract[ix[-1]]
        fp = np.nonzero([(t.hour * 60 + t.minute) >= flat.hour * 60 + flat.minute for t in start_local])[0]
        out.append(Session(cfg_s.get("name", ""), day, ix, start_local, int(fp[0]) if len(fp) else -1, ee, reason))
    return out
