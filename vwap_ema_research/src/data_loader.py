"""Carga, inspección, validación y construcción de velas de 15 min por instrumento.

Nunca se rellenan datos: filas inválidas se eliminan y se informan; los minutos que faltan se cuentan como huecos;
las sesiones incompletas se marcan como no válidas y no se operan. Si la calidad no llega al mínimo, DataQualityError.
"""
from __future__ import annotations

import glob
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import indicators as ind

COLS = ["open", "high", "low", "close", "volume"]
NOMBRES_TIEMPO = ("timestamp", "datetime", "date_time", "time", "date", "ts_event")


class DataQualityError(Exception):
    pass


def hhmm(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


def load(patron: str, base: Path, tz_si_naive: str = "UTC") -> pd.DataFrame:
    archivos = sorted(glob.glob(str(base / patron)))
    if not archivos:
        raise DataQualityError(f"No hay archivos que coincidan con '{patron}'.")
    partes = []
    for f in archivos:
        df = pd.read_parquet(f) if f.endswith(".parquet") else pd.read_csv(f)
        df.columns = [str(c).strip().lower().strip("<>") for c in df.columns]
        if not isinstance(df.index, pd.DatetimeIndex):
            col = next((c for c in NOMBRES_TIEMPO if c in df.columns), None)
            if col is None:
                raise DataQualityError(f"{Path(f).name}: sin columna de tiempo.")
            df.index = pd.to_datetime(df.pop(col))
        partes.append(df)
    df = pd.concat(partes)
    if "tickvol" in df.columns and "volume" not in df.columns:
        df["volume"] = df.pop("tickvol")
    faltan = [c for c in COLS if c not in df.columns]
    if faltan:
        raise DataQualityError(f"Faltan columnas: {faltan}")
    idx = df.index if df.index.tz is not None else df.index.tz_localize(tz_si_naive)
    df.index = idx.tz_convert("UTC")
    keep = COLS + (["instrument_id"] if "instrument_id" in df.columns else [])
    df = df[keep].copy()
    for c in COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.sort_index(kind="stable")


def inspect_and_clean(df: pd.DataFrame, max_invalid: float, nombre: str) -> tuple[pd.DataFrame, dict]:
    n0 = len(df)
    dup = df.index.duplicated(keep="last")
    df = df[~dup]
    nan = df[COLS].isna().any(axis=1)
    o, h, l, c, v = (df[k] for k in COLS)
    mal = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l) | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    inval = nan | mal | (v < 0)
    paso = pd.Series(df.index).diff().dropna()
    tf = paso.mode().iloc[0] if len(paso) else pd.NaT
    desal = ((df.index.second != 0) | ((df.index.minute % max(int(tf.total_seconds() // 60), 1)) != 0)).sum()
    info = {"instrumento": nombre, "simbolo_archivo": None, "timeframe_detectado": str(tf), "zona": "UTC",
            "desde": str(df.index.min()), "hasta": str(df.index.max()), "filas": n0, "duplicadas": int(dup.sum()),
            "nan": int(nan.sum()), "ohlc_inconsistente": int((mal & ~nan).sum()), "volumen_cero": int((v == 0).sum()),
            "timestamps_desalineados": int(desal), "invalidas_eliminadas": int(inval.sum()),
            "contratos": int(df.instrument_id.nunique()) if "instrument_id" in df else None}
    if inval.sum() / max(len(df), 1) > max_invalid:
        raise DataQualityError(f"{nombre}: {inval.mean():.3%} de filas inválidas.")
    return df[~inval], info


@dataclass
class Sesiones:
    bars: pd.DataFrame
    sub: dict
    info: dict


def build(df: pd.DataFrame, inst: dict, g: dict) -> Sesiones:
    """Velas de 15 min dentro de la sesión del instrumento, con VWAP de sesión calculado con los minutos."""
    tz, paso = inst["tz"], int(g["timeframe_minutes"])
    ini, fin = hhmm(inst["session"][0]), hhmm(inst["session"][1])
    loc = df.index.tz_convert(tz)
    t = loc.hour * 60 + loc.minute
    en = (t >= ini) & (t < fin)
    x = df[en]
    fecha = pd.Index(loc[en].date)
    k = (t[en] - ini) // paso
    ses_id = fecha.astype(str)
    vw = ind.vwap(x.high, x.low, x.close, x.volume, ses_id)
    tab = pd.DataFrame({"session": fecha, "k": k, "pos": np.arange(len(x)), "open": x.open.to_numpy(),
                        "high": x.high.to_numpy(), "low": x.low.to_numpy(), "close": x.close.to_numpy(),
                        "volume": x.volume.to_numpy(), "vwap": vw,
                        "inst": x.instrument_id.to_numpy() if "instrument_id" in x else 0})
    gr = tab.groupby(["session", "k"], sort=True)
    b = pd.DataFrame({"open": gr.open.first(), "high": gr.high.max(), "low": gr.low.min(), "close": gr.close.last(),
                      "volume": gr.volume.sum(), "n_sub": gr.pos.count(), "i0": gr.pos.first(), "i1": gr.pos.last(),
                      "vwap": gr.vwap.last(), "inst_first": gr.inst.first(), "inst_last": gr.inst.last()}).reset_index()
    base = pd.to_datetime(b.session.astype(str)) + pd.to_timedelta(ini + b.k * paso, unit="min")
    b["start"] = base.dt.tz_localize(tz, nonexistent="shift_forward", ambiguous="NaT").dt.tz_convert("UTC")
    b["start_min"] = ini + b.k * paso
    b["completeness"] = b.n_sub / paso
    esperadas = (fin - ini) // paso
    s = b.groupby("session").agg(n=("k", "count"), minc=("completeness", "min"))
    ok = (s.n == esperadas) & (s.minc >= g["min_bar_completeness"])
    b["session_valid"] = b.session.map(ok).astype(bool) & (pd.to_datetime(b.session.astype(str)).dt.dayofweek < 5).to_numpy()
    b["segment"] = ((b.inst_first != b.inst_last.shift()) | (b.inst_first != b.inst_last)).cumsum()
    minutos_esperados = len(s) * (fin - ini)
    if g.get("intrabar", "15m") == "15m":
        # Todo con velas de 15 min: VWAP con las velas de 15 min y stops/targets comprobados sobre la propia vela
        # (si una vela toca stop y target, se asume el stop).
        b["vwap"] = ind.vwap(b.high, b.low, b.close, b.volume, b.session.astype(str))
        b["i0"] = b["i1"] = np.arange(len(b))
        sub = {"open": b.open.to_numpy(), "high": b.high.to_numpy(), "low": b.low.to_numpy(),
               "close": b.close.to_numpy(), "time": b.start.dt.tz_localize(None).to_numpy()}
    else:
        sub = {"open": x.open.to_numpy(), "high": x.high.to_numpy(), "low": x.low.to_numpy(),
               "close": x.close.to_numpy(), "time": x.index.tz_localize(None).to_numpy()}
    info = {"sesiones": int(len(s)), "sesiones_validas": int(ok.sum()), "sesiones_excluidas": int((~ok).sum()),
            "velas_por_sesion": int(esperadas), "minutos_en_sesion_presentes_%": round(len(x) / max(minutos_esperados, 1) * 100, 2),
            "tramos_de_contrato": int(b.segment.nunique()),
            "cambios_de_contrato_dentro_de_vela": int((b.inst_first != b.inst_last).sum())}
    return Sesiones(b, sub, info)


def simbolo_de(patron: str) -> str:
    return re.split(r"[_.*]", Path(patron).name)[0]
