"""Calendario y construcción de velas de 15 min de la sesión regular (RTH).

- Las horas de sesión se interpretan en America/New_York con la zona horaria (el cambio de hora de EE. UU. y de
  Europa en fechas distintas no desplaza nada: todo se convierte vela a vela).
- Cada vela de 15 min se construye con las velas de la fuente cuyo inicio cae en [inicio, inicio + 15 min).
  Se conserva la posición de sus sub-velas para simular stops/targets dentro de la vela.
- VWAP: se calcula con las velas de la FUENTE (1 min si está disponible) y se toma el valor al cierre de la última
  sub-vela de cada vela de 15 min (incluida). Así no se usa información posterior al cierre de la vela.
- Cambios de contrato: el contrato continuo no se ajusta hacia atrás (ajustar el pasado usa información futura).
  Se crea un "tramo" nuevo cada vez que cambia instrument_id; ATR/EMA/RSI se reinician en cada tramo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind


def _minutos(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


@dataclass
class Sesiones:
    bars: pd.DataFrame          # una fila por vela de 15 min (RTH)
    sub: dict                   # arrays numpy de las sub-velas RTH: open, high, low, close, time (UTC)
    informe: dict


def build_bars(df: pd.DataFrame, cfg: dict) -> Sesiones:
    s, b = cfg["session"], cfg["bars"]
    tz, minutos = s["tz"], int(b["minutes"])
    src_min = int(cfg["data"]["source_bar_minutes"])
    if minutos % src_min:
        raise ValueError("La vela de decisión debe ser múltiplo de la vela de la fuente.")
    ny = df.index.tz_convert(tz)
    t = ny.hour * 60 + ny.minute
    ini, fin = _minutos(s["rth_start"]), _minutos(s["rth_end"])
    en_rth = (t >= ini) & (t < fin)
    fecha_rth = pd.Index(ny.date)

    # VWAP extendido (desde las 18:00 NY del día anterior) calculado con TODAS las velas de la fuente
    desfase = pd.Timedelta(minutes=24 * 60 - _minutos(s["extended_start"]))
    sesion_ext = pd.Index((ny + desfase).date)
    vw_ext_todo = ind.vwap(df.high, df.low, df.close, df.volume, sesion_ext.astype(str))

    rth = df[en_rth]
    fecha = fecha_rth[en_rth]
    mins = (t[en_rth] - ini)
    cubeta = mins // minutos
    vw_rth = ind.vwap(rth.high, rth.low, rth.close, rth.volume, pd.Index(fecha).astype(str))
    vw_ext = vw_ext_todo[en_rth]
    sd_rth = ind.vwap_std(rth.high, rth.low, rth.close, rth.volume, pd.Index(fecha).astype(str))

    tabla = pd.DataFrame({"session": fecha, "k": cubeta, "pos": np.arange(len(rth)), "open": rth.open.to_numpy(),
                          "high": rth.high.to_numpy(), "low": rth.low.to_numpy(), "close": rth.close.to_numpy(),
                          "volume": rth.volume.to_numpy(), "vwap_rth": vw_rth, "vwap_ext": vw_ext, "vwap_sd": sd_rth})
    if "instrument_id" in rth:
        tabla["inst"] = rth.instrument_id.to_numpy()
    else:
        tabla["inst"] = 0
    g = tabla.groupby(["session", "k"], sort=True)
    bars = pd.DataFrame({
        "open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
        "volume": g.volume.sum(), "n_sub": g.pos.count(), "i0": g.pos.first(), "i1": g.pos.last(),
        "vwap_rth": g.vwap_rth.last(), "vwap_ext": g.vwap_ext.last(), "vwap_sd": g.vwap_sd.last(),
        "inst_first": g.inst.first(), "inst_last": g.inst.last()}).reset_index()
    # Inicio de cada vela en UTC (desde la fecha y la cubeta, no desde la primera sub-vela)
    base = pd.to_datetime(bars.session.astype(str)) + pd.to_timedelta(ini + bars.k * minutos, unit="min")
    bars["start"] = base.dt.tz_localize(tz).dt.tz_convert("UTC")
    bars["start_ny_min"] = ini + bars.k * minutos
    bars["completeness"] = bars.n_sub / (minutos // src_min)

    # Validez de sesión: todas las velas presentes y suficientemente completas (excluye cierres anticipados)
    esperadas = (fin - ini) // minutos
    ses = bars.groupby("session").agg(n=("k", "count"), minc=("completeness", "min"))
    ok = (ses.n == esperadas) & (ses.minc >= s["min_bar_completeness"])
    bars["session_valid"] = bars.session.map(ok) if s["exclude_incomplete_sessions"] else True
    # Tramos de contrato: cambia cuando cambia el instrumento entre velas consecutivas o dentro de una vela
    cambio = (bars.inst_first != bars.inst_last.shift()) | (bars.inst_first != bars.inst_last)
    bars["segment"] = cambio.cumsum()
    bars["roll_in_bar"] = bars.inst_first != bars.inst_last

    sub = {"open": rth.open.to_numpy(), "high": rth.high.to_numpy(), "low": rth.low.to_numpy(),
           "close": rth.close.to_numpy(), "time": rth.index.tz_localize(None).to_numpy()}   # UTC sin zona
    informe = {"sesiones_rth": int(ses.shape[0]), "sesiones_validas": int(ok.sum()),
               "sesiones_excluidas": int((~ok).sum()), "velas_15m": int(len(bars)),
               "velas_por_sesion": int(esperadas), "tramos_de_contrato": int(bars.segment.nunique()),
               "cambios_de_contrato_dentro_de_vela": int(bars.roll_in_bar.sum())}
    return Sesiones(bars=bars, sub=sub, informe=informe)
