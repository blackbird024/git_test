"""Forward TEÓRICO (oficial): el código congelado de las dos supervivientes sobre datos que incluyen los días nuevos.

Las operaciones forward son las de ENTRADA >= inicio del forward (01/10/2026 00:00 NY). Los días anteriores solo sirven
de calentamiento (sigma de 14 días, SMA200...). Nada se ajusta.

Precios:
  - precio_teorico_* = precio de mercado del instante de ejecución SIN deslizamiento (apertura del minuto, o cierre de
    la vela de 15:59 en el cierre forzado de la zona de ruido; apertura de Globex en el RSI(2)).
  - precio_real_*    = precio con el deslizamiento que asume el backtest (el forward teórico no tiene fills reales; los
    fills reales vienen del EA, ver ea.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.core.datos import Contexto
from src.data.datos import excluidos
from src.strategies import nq_rsi2
from survivor.src import caracteristicas as CA
from survivor.src import congeladas as K
from survivor.src import trayectorias as TR

NY = "America/New_York"
TICK, PV = 0.25, 2.0
RASGOS_ZR = ["VOL_ATR", "VOL_REAL", "TENDENCIA", "atr14", "dist_vwap_atr", "dist_cierre_ant_atr", "hueco_atr", "apertura",
             "noche_ret_atr", "noche_rango_atr", "rango_previo_atr", "HORA", "DIA"]
RASGOS_RSI = ["VOL_ATR", "VOL_REAL", "TENDENCIA", "atr14", "rsi_senal", "dist_sma200_%", "ret_dia_atr", "dist_vwap_atr",
              "hueco_atr", "apertura", "noche_ret_atr", "noche_rango_atr", "rango_previo_atr", "DIA"]


def ultimo_dia_rth_completo(m1: pd.DataFrame) -> pd.Timestamp | None:
    ny = m1.index.tz_convert(NY)
    m = ny.hour * 60 + ny.minute
    fin = m1.index[(m >= 955) & (m < 960)]
    return None if len(fin) == 0 else pd.Timestamp(fin[-1].tz_convert(NY).date())


def calcular(m1: pd.DataFrame, inicio_forward: pd.Timestamp, excluir: frozenset | None = None) -> dict:
    """Devuelve {'NOISE_ZONE': df, 'RSI2': df} con TODAS las operaciones de entrada >= inicio_forward (cerradas y
    abiertas) y el día RTH completo más reciente."""
    excluir = excluidos("NQ") if excluir is None else excluir
    inicio_utc = pd.Timestamp(inicio_forward).tz_localize(NY).tz_convert("UTC")
    ultimo = ultimo_dia_rth_completo(m1)
    ctx = Contexto(m1, excluir)
    d = CA.tabla_diaria(ctx)
    out = {"ultimo_dia_completo": ultimo}
    # ---------------- zona de ruido
    zr = K.zona_ruido(m1, excluir)
    zr = zr[zr.t_entrada >= inicio_utc].reset_index(drop=True)
    if ultimo is not None:
        fecha_zr = pd.DatetimeIndex(zr.t_entrada).tz_convert(NY).tz_localize(None).normalize()
        zr = zr[fecha_zr <= ultimo].reset_index(drop=True)          # un día RTH incompleto no se registra
    out["NOISE_ZONE"] = _registros_zr(ctx, zr, d) if len(zr) else pd.DataFrame()
    # ---------------- RSI(2)
    rs_todas = K.rsi2(m1, excluir)
    s = nq_rsi2.preparar(m1, K.RSI2_SURVIVOR_V1)
    rs = rs_todas[rs_todas.t_entrada >= inicio_utc].reset_index(drop=True)
    out["RSI2"] = _registros_rsi(ctx, rs, d, s) if len(rs) else pd.DataFrame()
    out["senal_rsi2_pendiente"] = _senal_pendiente(s, rs_todas)
    return out


def _base(ops, estrategia):
    te = pd.DatetimeIndex(ops.t_entrada).tz_convert("UTC")
    ts = pd.DatetimeIndex(ops.t_salida).tz_convert("UTC")
    return pd.DataFrame({
        "id": [f"{estrategia}|{t:%Y-%m-%dT%H:%M}Z" for t in te], "estrategia": estrategia,
        "t_entrada_utc": te, "t_salida_utc": ts,
        "t_entrada_ny": te.tz_convert(NY).strftime("%Y-%m-%d %H:%M"), "t_salida_ny": ts.tz_convert(NY).strftime("%Y-%m-%d %H:%M"),
        "duracion_min": ((ts - te).total_seconds() / 60).round(1)})


def _registros_zr(ctx, zr: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    r = _base(zr, "NOISE_ZONE")
    dirc = zr.direccion.to_numpy()
    r["fecha_sesion"] = pd.DatetimeIndex(zr.t_entrada).tz_convert(NY).strftime("%Y-%m-%d")
    r["sesion"] = "RTH NY (intradía)"
    r["direccion"] = np.where(dirc == 1, "LARGO", "CORTO")
    i = np.searchsorted(ctx.t.asi8, pd.DatetimeIndex(r.t_entrada_utc).asi8)
    r["contrato"] = [f"MNQ (NQ.v.0 instrument_id {x})" for x in ctx.m1.instrument_id.to_numpy()[i]] if "instrument_id" in ctx.m1 else "MNQ"
    r["contratos"] = 1
    r["precio_teorico_entrada"] = zr.entrada.to_numpy() - dirc * TICK * K.NOISE_ZONE_SURVIVOR_V1.ticks_entrada
    r["precio_real_entrada"] = zr.entrada.to_numpy()
    r["precio_teorico_salida"] = zr.salida.to_numpy() + dirc * TICK * K.NOISE_ZONE_SURVIVOR_V1.ticks_salida
    r["precio_real_salida"] = zr.salida.to_numpy()
    r["slippage_ticks"] = K.NOISE_ZONE_SURVIVOR_V1.ticks_entrada + K.NOISE_ZONE_SURVIVOR_V1.ticks_salida
    r["slippage_$"] = r.slippage_ticks * TICK * PV
    r["comision_$"] = zr.comision.to_numpy()
    r["bruto_sin_costes_$"] = dirc * (r.precio_teorico_salida - r.precio_teorico_entrada) * PV
    r["bruto_$"] = zr.bruto.to_numpy()
    r["neto_$"] = zr.neto.to_numpy()
    r["neto_%"] = r["neto_$"] / (r.precio_real_entrada * PV) * 100
    tr = TR.zona_ruido(ctx, zr)
    r["mae_pts"], r["mfe_pts"] = tr.mae_pts.to_numpy(), tr.mfe_pts.to_numpy()
    r["motivo"] = zr.motivo.to_numpy()
    r["estado"] = "CERRADA"
    f = CA.zona_ruido(ctx, zr, d)
    for c in RASGOS_ZR:
        r[c] = f[c].to_numpy()
    return r


def _registros_rsi(ctx, rs: pd.DataFrame, d: pd.DataFrame, s: pd.DataFrame) -> pd.DataFrame:
    r = _base(rs, "RSI2")
    t0 = pd.DatetimeIndex(s.t_primera).asi8
    e = np.searchsorted(t0, pd.DatetimeIndex(rs.t_entrada).asi8)
    x = np.searchsorted(t0, pd.DatetimeIndex(rs.t_salida).asi8)
    cfg = K.RSI2_SURVIVOR_V1
    r["fecha_sesion"] = [str(s.index[k].date()) for k in e]
    r["sesion"] = "CME completa (mantiene de noche)"
    r["direccion"] = "LARGO"
    r["contrato"] = [f"MNQ (NQ.v.0 instrument_id {s.primer_id.iloc[k]})" for k in e]
    r["contratos"] = 1
    r["precio_teorico_entrada"] = s.open.to_numpy()[e]
    r["precio_teorico_salida"] = s.open.to_numpy()[x]
    t_e = [pd.Timestamp(v) for v in rs.t_entrada]
    t_x = [pd.Timestamp(v) for v in rs.t_salida]
    tk_e = np.array([cfg.costes.ticks(t) for t in t_e])
    tk_x = np.array([cfg.costes.ticks(t) for t in t_x])
    r["precio_real_entrada"] = r.precio_teorico_entrada + tk_e * TICK
    r["precio_real_salida"] = r.precio_teorico_salida - tk_x * TICK
    r["slippage_ticks"] = tk_e + tk_x
    r["slippage_$"] = r.slippage_ticks * TICK * PV
    r["comision_$"] = cfg.costes.comision(1)
    ret_bruto = s.open_aj.to_numpy()[x] / s.open_aj.to_numpy()[e] - 1       # serie ajustada (sin saltos de roll)
    r["bruto_sin_costes_$"] = r.precio_teorico_entrada * ret_bruto * PV
    r["bruto_$"] = r["bruto_sin_costes_$"] - r["slippage_$"]
    r["neto_$"] = rs.neto.to_numpy()
    r["neto_%"] = r["neto_$"] / (r.precio_teorico_entrada * PV) * 100      # = ret_% neto del backtest
    tr = TR.rsi2(rs, s)
    r["mae_pts"] = (tr["mae_%"] / 100 * r.precio_teorico_entrada).to_numpy()
    r["mfe_pts"] = (tr["mfe_%"] / 100 * r.precio_teorico_entrada).to_numpy()
    r["ret_%"] = rs["ret_%"].to_numpy()
    r["sesiones"] = rs.sesiones.to_numpy()
    r["motivo"] = rs.motivo.to_numpy()
    r["estado"] = np.where(rs.motivo == "fin_de_datos", "ABIERTA", "CERRADA")
    f = CA.rsi2(ctx, rs, d, s)
    for c in RASGOS_RSI:
        r[c] = f[c].to_numpy()
    return r


def _senal_pendiente(s: pd.DataFrame, rs_todas: pd.DataFrame) -> dict:
    """Señal del RSI(2) en la última sesión cerrada (entraría en la próxima reapertura). Solo informativo."""
    t_fin = pd.DatetimeIndex(s.t_ultima).tz_convert(NY)
    completas = np.flatnonzero((t_fin.hour >= 16) | ((t_fin.hour == 13) & (t_fin.minute >= 10)))   # sesión cerrada (o media)
    k = completas[-1] if len(completas) else len(s) - 1
    ult = s.iloc[k]
    abierta = len(rs_todas) and rs_todas.motivo.iloc[-1] == "fin_de_datos"
    return {"sesion": str(s.index[k].date()), "rsi2": round(float(ult.rsi), 2), "sobre_sma200": bool(ult.close_aj > ult.sma),
            "senal_de_entrada": bool(ult.senal) and not abierta, "posicion_abierta": bool(abierta)}
