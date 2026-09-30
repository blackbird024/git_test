"""Cartera de las dos supervivientes a IGUAL RIESGO (PRE-REGISTRO §7), mark-to-market diario del RSI(2), correlaciones
(globales, mensuales, de drawdown y condicionadas) y solapamiento."""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot_lab.validation.montecarlo import trayectorias

TICK, PV = 0.25, 2.0


def rsi2_mtm(ops: pd.DataFrame, s: pd.DataFrame, costes) -> pd.Series:
    """P&L diario mark-to-market del RSI(2): cambio de valor al cierre de cada sesión en posición; la salida (apertura
    de la sesión x, 18:00 NY del mismo día natural que el cierre de x-1) y todos los costes se apuntan en la fecha de x-1.
    Suma exactamente el neto de cada operación."""
    t0 = pd.DatetimeIndex(s.t_primera).asi8
    e = np.searchsorted(t0, pd.DatetimeIndex(ops.t_entrada).asi8)
    x = np.searchsorted(t0, pd.DatetimeIndex(ops.t_salida).asi8)
    oa, ca, o = s.open_aj.to_numpy(), s.close_aj.to_numpy(), s.open.to_numpy()
    fechas = s.index
    pnl = pd.Series(0.0, index=fechas)
    for j in range(len(ops)):
        a, b = e[j], x[j]
        base = o[a] * PV / oa[a]                        # $ por punto ajustado
        valor = 0.0
        for k in range(a, b):
            v = (ca[k] - oa[a]) * base
            pnl.iloc[k] += v - valor
            valor = v
        final = (oa[b] - oa[a]) * base
        costes_op = (final + 0) - ops.neto.iloc[j]     # desl + comisión exactos del original
        pnl.iloc[max(b - 1, a)] += final - valor - costes_op
    return pnl


def pesos(d: pd.DataFrame, corte: pd.Timestamp, reparto: float) -> tuple[float, float]:
    """Reparto de riesgo zr:rsi = reparto:(1-reparto); w_i ∝ reparto_i/σ_i con σ de DESARROLLO (< corte); reescalado
    para que la volatilidad diaria de la cartera (en desarrollo) = σ de la ZR sola con 1 MNQ."""
    dev = d[d.index < corte]
    sz, sr = dev.zr.std(), dev.rsi2.std()
    if reparto == 1:
        return 1.0, 0.0
    if reparto == 0:
        return 0.0, round(sz / sr, 3)
    wz, wr = reparto / sz, (1 - reparto) / sr
    k = sz / (wz * dev.zr + wr * dev.rsi2).std()
    return round(wz * k, 3), round(wr * k, 3)


def metricas(p: pd.Series, capital: float) -> dict:
    eq = p.cumsum()
    dd = eq - np.maximum.accumulate(np.r_[0.0, eq.to_numpy()])[1:]
    anios = len(p) / 252
    anual = p.groupby(p.index.year).sum()
    mes = p.resample("ME").sum()
    sd, abajo = p.std(), np.sqrt(np.mean(np.minimum(p, 0) ** 2))
    return {"rentabilidad_anual_%": round(p.sum() / anios / capital * 100, 2), "sharpe": round(p.mean() / sd * np.sqrt(252), 2),
            "sortino": round(p.mean() / abajo * np.sqrt(252), 2), "max_dd_$": round(dd.min(), 0),
            "calmar": round(p.sum() / anios / -dd.min(), 2), "peor_año_$": round(anual.min(), 0),
            "años_negativos_%": round((anual < 0).mean() * 100, 1), "peor_mes_$": round(mes.min(), 0)}


def montecarlo(p: pd.Series, n: int, semilla: int, limite_dia: float = 1000, caida: float = 5000) -> dict:
    s = trayectorias(p, 20, n, 252, semilla)
    eq = np.cumsum(s, axis=1)
    dd = (eq - np.maximum.accumulate(np.concatenate([np.zeros((n, 1)), eq], axis=1), axis=1)[:, 1:]).min(axis=1)
    return {"MC_DD_p50_$": round(np.percentile(dd, 50), 0), "MC_DD_p95_$": round(np.percentile(dd, 5), 0),
            "MC_DD_p99_$": round(np.percentile(dd, 1), 0), "P(año negativo)_%": round((eq[:, -1] < 0).mean() * 100, 1),
            f"P(DD ≥ {caida:.0f} $)_%": round((dd <= -caida).mean() * 100, 1),
            f"P(algún día ≤ −{limite_dia:.0f} $)_%": round((s <= -limite_dia).any(axis=1).mean() * 100, 1)}


def correlaciones(d: pd.DataFrame) -> dict:
    eq = d.cumsum()
    dd = eq - eq.cummax()
    ambos = d[(d.zr != 0) & (d.rsi2 != 0)]
    return {"diaria": round(d.zr.corr(d.rsi2), 3), "diaria_dias_con_ambas": round(ambos.zr.corr(ambos.rsi2), 3),
            "dias_con_ambas": len(ambos), "mensual": round(d.resample("ME").sum().corr().iloc[0, 1], 3),
            "drawdown": round(dd.zr.corr(dd.rsi2), 3)}


def condicionadas(d: pd.DataFrame, etiquetas: pd.DataFrame) -> pd.DataFrame:
    filas = {}
    for col in etiquetas.columns:
        for k in pd.unique(etiquetas[col]):
            m = (etiquetas[col] == k).to_numpy()
            x = d[m]
            ambos = x[(x.zr != 0) & (x.rsi2 != 0)]
            filas[f"{col} = {k}"] = {"dias": int(m.sum()), "corr_todos_los_dias": round(x.zr.corr(x.rsi2), 3) if m.sum() > 20 else np.nan,
                                     "dias_con_ambas": len(ambos),
                                     "corr_dias_con_ambas": round(ambos.zr.corr(ambos.rsi2), 3) if len(ambos) > 20 else np.nan}
    return pd.DataFrame(filas).T


def solapamiento(zr: pd.DataFrame, rs: pd.DataFrame) -> dict:
    ini, fin = rs.t_entrada.to_numpy(), rs.t_salida.to_numpy()
    sol = np.zeros(len(zr), bool)
    for i, (a, b) in enumerate(zip(zr.t_entrada.to_numpy(), zr.t_salida.to_numpy())):
        sol[i] = ((ini < b) & (fin > a)).any()
    mismo = sol & (zr.direccion.to_numpy() == 1)
    opuesto = sol & (zr.direccion.to_numpy() == -1)
    dias_zr = set(pd.DatetimeIndex(zr.t_entrada).tz_convert("America/New_York").date)
    dias_rs = set()
    for a, b in zip(rs.t_entrada, rs.t_salida):
        dias_rs.update(pd.date_range(a.tz_convert("America/New_York").normalize(), b.tz_convert("America/New_York").normalize()).date)
    return {"operaciones_ZR": len(zr), "ZR_con_RSI2_abierto": int(sol.sum()), "mismo_sentido (ZR largo)": int(mismo.sum()),
            "sentido_opuesto (ZR corto)": int(opuesto.sum()), "neto_medio_ZR_mismo_sentido_$": round(zr.neto[mismo].mean(), 2),
            "neto_medio_ZR_sentido_opuesto_$": round(zr.neto[opuesto].mean(), 2),
            "neto_medio_ZR_sin_RSI2_$": round(zr.neto[~sol].mean(), 2),
            "dias_con_ZR": len(dias_zr), "dias_con_RSI2_abierto": len(dias_rs), "dias_con_ambas": len(dias_zr & dias_rs)}
