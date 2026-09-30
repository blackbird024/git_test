"""Regímenes (fijos, sin optimizar; CRITERIOS.md §6) y estudios por hora (BOT 21) y día de la semana (BOT 22).

Régimen de cada día NY, calculado con la sesión RTH ANTERIOR (causal):
  - volatilidad: ATR(14) diario / ATR(250) diario -> BAJA (< 0,8), NORMAL, ALTA (> 1,2)
  - tendencia: ratio de eficiencia de 20 sesiones (|C − C_20| / suma |ΔC|) -> TENDENCIA (> 0,3) o RANGO
Franja de la entrada (hora NY): noche 18-03, Londres 03-08, pre-apertura/solape 08-09:30, apertura NY 09:30-10:30,
mañana NY 10:30-11:30, mediodía 11:30-14:00, tarde 14:00-16:00, cierre/otras 16-18.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind
from bot_lab.strategies import base as B

FRANJAS = [("noche", 18 * 60, 24 * 60), ("noche", 0, 180), ("Londres", 180, 480), ("pre-apertura/solape", 480, 570),
           ("apertura NY", 570, 630), ("mañana NY", 630, 690), ("mediodía NY", 690, 840), ("tarde NY", 840, 960),
           ("cierre/otras", 960, 1080)]
ORDEN_FRANJAS = ["noche", "Londres", "pre-apertura/solape", "apertura NY", "mañana NY", "mediodía NY", "tarde NY",
                 "cierre/otras"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def diario_rth(ctx) -> pd.DataFrame:
    def f():
        idx = np.flatnonzero(ctx.rth)
        a = ctx.desfase[idx]
        df = pd.DataFrame({"f": ctx.fecha[idx], "o": ctx.O[idx] - a, "h": ctx.H[idx] - a, "l": ctx.L[idx] - a,
                           "c": ctx.C[idx] - a})
        g = df.groupby("f")
        d = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
        d.index = pd.DatetimeIndex(d.index)
        return d
    return B.cache(ctx, "diario_rth", f)


def tabla_regimenes(ctx, cfg: dict) -> pd.DataFrame:
    def f():
        d = diario_rth(ctx)
        h, l, c = d.h.to_numpy(), d.l.to_numpy(), d.c.to_numpy()
        ratio = ind.atr(h, l, c, 14) / ind.atr(h, l, c, 250)
        cambio = pd.Series(c).diff().abs()
        er = (pd.Series(c) - pd.Series(c).shift(20)).abs() / cambio.rolling(20).sum()
        out = pd.DataFrame({"ratio_vol": ratio, "er20": er.to_numpy()}, index=d.index).shift(1)   # causal
        out["vol"] = np.where(out.ratio_vol < cfg["vol_baja"], "BAJA",
                              np.where(out.ratio_vol > cfg["vol_alta"], "ALTA", "NORMAL"))
        out.loc[out.ratio_vol.isna(), "vol"] = "sin dato"
        out["tendencia"] = np.where(out.er20 > cfg["er_tendencia"], "TENDENCIA", "RANGO")
        out.loc[out.er20.isna(), "tendencia"] = "sin dato"
        return out
    return B.cache(ctx, "regimenes", f)


def franja(minuto: np.ndarray) -> np.ndarray:
    out = np.empty(len(minuto), dtype=object)
    for nombre, a, b in FRANJAS:
        out[(minuto >= a) & (minuto < b)] = nombre
    return out


def etiquetar(ops: pd.DataFrame, ctx, cfg: dict) -> pd.DataFrame:
    """Añade régimen de volatilidad, tendencia, franja, día de la semana y año (según la ENTRADA, hora NY)."""
    if len(ops) == 0:
        return ops.assign(vol=[], tendencia=[], franja=[], dia=[], año=[])
    t = pd.DatetimeIndex(ops.t_entrada).tz_convert("America/New_York")
    fecha = t.tz_localize(None).normalize()
    reg = tabla_regimenes(ctx, cfg)
    # un día sin sesión RTH (domingo por la tarde) toma el régimen del siguiente día con sesión
    pos = np.searchsorted(reg.index.to_numpy(), fecha.to_numpy(), side="left").clip(0, len(reg) - 1)
    o = ops.copy()
    o["vol"] = reg.vol.to_numpy()[pos]
    o["tendencia"] = reg.tendencia.to_numpy()[pos]
    o["franja"] = franja((t.hour * 60 + t.minute).to_numpy())
    o["dia"] = [DIAS[d] for d in t.weekday]
    o["año"] = t.year
    return o


def por_grupo(ops: pd.DataFrame, col: str, orden=None) -> pd.DataFrame:
    if len(ops) == 0:
        return pd.DataFrame()
    g = ops.groupby(col)
    t = pd.DataFrame({
        "operaciones": g.size(), "neto_$": g.neto.sum().round(0), "expectativa_$": g.neto.mean().round(2),
        "t": g.neto.apply(lambda s: round(s.mean() / s.std(ddof=1) * np.sqrt(len(s)), 2) if len(s) > 2 and s.std() > 0 else np.nan),
        "PF": g.neto.apply(lambda s: round(s[s > 0].sum() / -s[s < 0].sum(), 2) if (s < 0).any() else np.inf)})
    if orden:
        t = t.reindex([x for x in orden if x in t.index])
    return t


def deriva_por_franja(ctx, hasta_tramo: int = 0) -> pd.DataFrame:
    """BOT 21 (investigación): cambio medio de NQ (en $ por 1 MNQ, sin costes) de estar comprado en cada franja,
    por día, solo en los tramos <= hasta_tramo. Se descartan los días con cambio de contrato dentro de la franja."""
    filas = []
    fr = franja(ctx.min_ny)
    clave = pd.Series(ctx.ses_fecha.astype(np.int64)).astype(str) + "|" + pd.Series(fr).astype(str)
    df = pd.DataFrame({"k": clave, "o": ctx.O, "c": ctx.C, "a": ctx.desfase, "tramo": ctx.tramo, "fr": fr})
    df = df[df.tramo <= hasta_tramo]
    g = df.groupby("k", sort=False)
    r = pd.DataFrame({"fr": g.fr.first(), "o": g.o.first(), "c": g.c.last(), "a0": g.a.first(), "a1": g.a.last()})
    r = r[r.a0 == r.a1]
    r["usd"] = (r.c - r.o) * 2.0
    for nombre in ORDEN_FRANJAS:
        x = r.usd[r.fr == nombre]
        if len(x) < 3:
            continue
        filas.append({"franja": nombre, "días": len(x), "media_$": round(x.mean(), 2),
                      "t": round(x.mean() / x.std(ddof=1) * np.sqrt(len(x)), 2), "%_positivos": round((x > 0).mean() * 100, 1)})
    return pd.DataFrame(filas).set_index("franja")


def deriva_por_dia(ctx, hasta_tramo: int = 0) -> pd.DataFrame:
    """BOT 22 (investigación): cambio medio apertura->cierre RTH por día de la semana ($ por 1 MNQ, sin costes)."""
    d = diario_rth(ctx)
    tr = pd.Series(ctx.tramo, index=pd.DatetimeIndex(ctx.fecha)).groupby(level=0).first().reindex(d.index)
    d = d[tr <= hasta_tramo]
    usd = (d.c - d.o) * 2.0
    filas = []
    for k in range(5):
        x = usd[d.index.weekday == k]
        filas.append({"día": DIAS[k], "días": len(x), "media_$": round(x.mean(), 2),
                      "t": round(x.mean() / x.std(ddof=1) * np.sqrt(len(x)), 2), "%_positivos": round((x > 0).mean() * 100, 1)})
    return pd.DataFrame(filas).set_index("día")
