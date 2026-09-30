"""Rasgos PREVIOS a la entrada de cada operación (PRE-REGISTRO §2). Nunca usan información posterior a la entrada.

Tabla diaria RTH (precios ajustados de forma causal por cambio de contrato, bot_lab/core/datos.py): los valores de la
fila D se conocen al CIERRE RTH del día D.
  - Zona de ruido (entra el día D entre 10:00 y 15:30): usa la fila D-1 para régimen y los datos de D hasta antes de las
    10:00 (hueco, apertura, noche) y el minuto anterior a la entrada (VWAP).
  - RSI(2) (señal al cierre de la sesión de CME del día D, entrada 18:00): usa la fila D (sesión que acaba de cerrar).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core import indicadores as ind

NY = "America/New_York"


def tabla_diaria(ctx) -> pd.DataFrame:
    idx = np.flatnonzero(ctx.rth)
    a = ctx.desfase[idx]
    df = pd.DataFrame({"f": ctx.fecha[idx], "o": ctx.O[idx] - a, "h": ctx.H[idx] - a, "l": ctx.L[idx] - a,
                       "c": ctx.C[idx] - a})
    g = df.groupby("f")
    d = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    d.index = pd.DatetimeIndex(d.index)
    h, l, c = d.h.to_numpy(), d.l.to_numpy(), d.c.to_numpy()
    d["atr14"] = ind.atr(h, l, c, 14)
    d["ratio_vol"] = d.atr14 / ind.atr(h, l, c, 250)
    r = np.log(d.c).diff()
    d["ret1"] = r
    d["rv20"] = r.rolling(20).std()
    d["ret20"] = d.c - d.c.shift(20)
    d["er20"] = d.ret20.abs() / d.c.diff().abs().rolling(20).sum()
    d["rango"] = d.h - d.l
    # Noche (18:00 del día anterior -> 09:29) de la sesión de CME con fecha D, ajustada
    noche = ~ctx.rth & ((ctx.min_ny >= 1080) | (ctx.min_ny < 570))
    k = np.flatnonzero(noche)
    ak = ctx.desfase[k]
    n = pd.DataFrame({"s": ctx.ses_fecha[k], "o": ctx.O[k] - ak, "h": ctx.H[k] - ak, "l": ctx.L[k] - ak, "c": ctx.C[k] - ak})
    gn = n.groupby("s")
    noche_d = pd.DataFrame({"on_o": gn.o.first(), "on_c": gn.c.last(), "on_h": gn.h.max(), "on_l": gn.l.min(), "on_n": gn.o.size()})
    noche_d.index = pd.DatetimeIndex(noche_d.index)
    d = d.join(noche_d)
    # Cuantiles EXPANSIVOS (solo historia hasta el día, mínimo 250 días): causales
    exp = lambda s, q: s.expanding(250).quantile(q)  # noqa: E731
    d["rv20_q33"], d["rv20_q67"], d["rv20_q95"] = exp(d.rv20, 1 / 3), exp(d.rv20, 2 / 3), exp(d.rv20, 0.95)
    d["ret1_q02"] = exp(d.ret1, 0.02)
    d["ret20abs_q95"] = exp((d.ret20 / d.c.shift(20)).abs(), 0.95)
    d["ret20_pct"] = d.ret20 / d.c.shift(20)
    return d


def clases_regimen(fila: pd.DataFrame) -> pd.DataFrame:
    """Clases de régimen a partir de filas de la tabla diaria (ya alineadas con cada operación)."""
    out = pd.DataFrame(index=fila.index)
    rv = fila.ratio_vol
    out["VOL_ATR"] = np.select([rv < 0.8, rv > 1.2, rv.notna()], ["BAJA", "ALTA", "NORMAL"], "sin dato")
    out["VOL_REAL"] = np.select([fila.rv20 <= fila.rv20_q33, fila.rv20 > fila.rv20_q67, fila.rv20_q33.notna()],
                                ["baja", "alta", "media"], "sin dato")
    up = (fila.er20 > 0.3) & (fila.ret20 > 0)
    dn = (fila.er20 > 0.3) & (fila.ret20 < 0)
    out["TENDENCIA"] = np.select([up, dn, fila.er20.notna()], ["TREND UP", "TREND DOWN", "RANGE"], "sin dato")
    rango_rel = fila.rango / fila.atr14
    out["RANGO_PREVIO"] = np.select([rango_rel < 0.8, rango_rel > 1.2, rango_rel.notna()],
                                    ["contracción", "expansión", "normal"], "sin dato")
    out["CRISIS_VOL"] = (fila.rv20 >= fila.rv20_q95) & fila.rv20_q95.notna()
    out["CRISIS_CRASH"] = (fila.ret1 <= fila.ret1_q02) & fila.ret1_q02.notna()
    out["CRISIS_TENDENCIA"] = (fila.ret20_pct.abs() >= fila.ret20abs_q95) & fila.ret20abs_q95.notna()
    out["atr14"] = fila.atr14.to_numpy()
    return out


def terciles(x: pd.Series, etiquetas=("bajo", "medio", "alto")) -> np.ndarray:
    """Terciles DESCRIPTIVOS dentro de las operaciones de una estrategia (usan toda la muestra: no son causales ni se
    usan como filtro; sirven solo para describir)."""
    try:
        return pd.qcut(x, 3, labels=list(etiquetas)).astype(str).to_numpy()
    except ValueError:
        return np.full(len(x), "sin dato")


def _pos_apertura(o, ph, pl):
    return np.select([o > ph, o >= (ph + pl) / 2, o >= pl, o < pl], ["encima del máx.", "mitad alta", "mitad baja",
                                                                      "debajo del mín."], "sin dato")


def zona_ruido(ctx, ops: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    t = pd.DatetimeIndex(ops.t_entrada)
    ny = t.tz_convert(NY)
    fecha = pd.DatetimeIndex(ny.tz_localize(None).normalize())
    pos = d.index.get_indexer(fecha)
    assert (pos > 0).all(), "cada operación debe tener su día RTH"
    hoy, ayer = d.iloc[pos].reset_index(drop=True), d.iloc[pos - 1].reset_index(drop=True)
    f = clases_regimen(ayer)
    atr = ayer.atr14.to_numpy()
    i_ent = np.searchsorted(ctx.t.asi8, t.asi8)
    i_sig = i_ent - 1
    vw = ctx.vwap_rth[0][i_sig]
    dirc = ops.direccion.to_numpy()
    f["dist_vwap_atr"] = dirc * (ctx.C[i_sig] - vw) / atr
    f["dist_cierre_ant_atr"] = dirc * ((ctx.C[i_sig] - ctx.desfase[i_sig]) - ayer.c.to_numpy()) / atr
    f["hueco_atr"] = (hoy.o.to_numpy() - ayer.c.to_numpy()) / atr
    f["hueco_a_favor"] = np.sign(f.hueco_atr) == dirc
    f["apertura"] = _pos_apertura(hoy.o.to_numpy(), ayer.h.to_numpy(), ayer.l.to_numpy())
    f["noche_ret_atr"] = dirc * (hoy.on_c - hoy.on_o).to_numpy() / atr
    f["noche_rango_atr"] = (hoy.on_h - hoy.on_l).to_numpy() / atr
    f["rango_previo_atr"] = (ayer.rango / ayer.atr14).to_numpy()
    minuto = (ny.hour * 60 + ny.minute).to_numpy()
    f["HORA"] = np.select([minuto < 630, minuto < 690, minuto < 840], ["10:00", "10:30-11:00", "11:30-13:30 mediodía"],
                          "14:00-15:30 tarde")
    f["DIA"] = np.array(["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"])[ny.weekday]
    for col, nombre in (("dist_vwap_atr", "VWAP"), ("hueco_atr", "HUECO"), ("noche_ret_atr", "NOCHE_RET"),
                        ("noche_rango_atr", "NOCHE_RANGO"), ("dist_cierre_ant_atr", "DIST_CIERRE_ANT")):
        base = f[col].abs() if col in ("dist_vwap_atr", "hueco_atr") else f[col]
        f[nombre] = terciles(base, ("cerca", "moderado", "extremo") if col == "dist_vwap_atr" else ("bajo", "medio", "alto"))
    f["LADO"] = np.where(dirc == 1, "LARGO", "CORTO")
    return f


def rsi2(ctx, ops: pd.DataFrame, d: pd.DataFrame, sesiones: pd.DataFrame) -> pd.DataFrame:
    """sesiones: tabla de nq_rsi2.preparar (rsi, sma, close_aj...) indexada por fecha de sesión de CME."""
    t_sig = pd.DatetimeIndex(ops.t_senal).tz_convert(NY) if pd.DatetimeIndex(ops.t_senal).tz else pd.DatetimeIndex(ops.t_senal).tz_localize("UTC").tz_convert(NY)
    fecha = pd.DatetimeIndex(t_sig.tz_localize(None).normalize())
    pos = d.index.get_indexer(fecha)
    ok = pos >= 1
    hoy = d.iloc[np.where(ok, pos, 1)].reset_index(drop=True)
    ayer = d.iloc[np.where(ok, pos - 1, 0)].reset_index(drop=True)
    f = clases_regimen(hoy)
    atr = hoy.atr14.to_numpy()
    s = sesiones.reindex(fecha)
    f["rsi_senal"] = s.rsi.to_numpy()
    f["RSI_NIVEL"] = np.select([f.rsi_senal < 5, f.rsi_senal < 10], ["< 5", "5-10"], "10-20")
    f["dist_sma200_%"] = ((s.close_aj / s.sma - 1) * 100).to_numpy()
    f["DIST_SMA200"] = terciles(f["dist_sma200_%"])
    f["ret_dia_atr"] = ((hoy.c - ayer.c) / hoy.atr14).to_numpy()
    f["MOV_PREVIO"] = terciles(-f.ret_dia_atr, ("caída pequeña", "caída media", "caída grande"))
    # VWAP de la sesión de CME al cierre (VWAP Globex acumulado en el último minuto de la sesión)
    i_ult = np.searchsorted(ctx.t.asi8, pd.DatetimeIndex(ops.t_senal).asi8)
    f["dist_vwap_atr"] = (ctx.C[i_ult] - ctx.vwap_globex[0][i_ult]) / atr
    f["VWAP"] = terciles(f.dist_vwap_atr.abs(), ("cerca", "moderado", "extremo"))
    f["hueco_atr"] = (hoy.o - ayer.c).to_numpy() / atr
    f["HUECO"] = terciles(f.hueco_atr)
    f["apertura"] = _pos_apertura(hoy.o.to_numpy(), ayer.h.to_numpy(), ayer.l.to_numpy())
    f["noche_ret_atr"] = (hoy.on_c - hoy.on_o).to_numpy() / atr
    f["NOCHE_RET"] = terciles(f.noche_ret_atr)
    f["noche_rango_atr"] = (hoy.on_h - hoy.on_l).to_numpy() / atr
    f["NOCHE_RANGO"] = terciles(f.noche_rango_atr)
    f["rango_previo_atr"] = (hoy.rango / hoy.atr14).to_numpy()
    f["DIA"] = np.array(["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"])[pd.DatetimeIndex(ops.t_entrada).tz_convert(NY).weekday]
    f["HORA"] = "18:00 (siempre)"
    f["LADO"] = "LARGO"
    return f
