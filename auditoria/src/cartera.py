"""Fases 7-8: cartera zona de ruido + RSI(2) y simulación de riesgo.

Modelo de capital: capital fijo (sin reinvertir), P&L diario en $ por día de SALIDA (hora NY) con 1 MNQ por unidad
de peso; el capital no usado no rinde nada. Los pesos son "contratos equivalentes" (fraccionarios en la simulación;
en real solo hay contratos enteros).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metricas as mt


def series(zr: pd.DataFrame, rs: pd.DataFrame, sesiones: pd.DatetimeIndex) -> pd.DataFrame:
    a, b = mt.diario(zr, sesiones), mt.diario(rs, sesiones)
    d = pd.DataFrame({"zona": a.pnl, "rsi2": b.pnl}).fillna(0.0)
    return d


def solapamiento(zr: pd.DataFrame, rs: pd.DataFrame) -> dict:
    """Operaciones de la zona de ruido durante las que había una posición del RSI(2) abierta."""
    ini_r, fin_r = rs.t_entrada.to_numpy(), rs.t_salida.to_numpy()
    solapa = np.zeros(len(zr), bool)
    for i, (a, b) in enumerate(zip(zr.t_entrada.to_numpy(), zr.t_salida.to_numpy())):
        solapa[i] = ((ini_r < b) & (fin_r > a)).any()
    mismo = solapa & (zr.direccion.to_numpy() == 1)                   # el RSI(2) solo compra
    horas_zr = ((zr.t_salida - zr.t_entrada).dt.total_seconds() / 3600).to_numpy()
    return {"operaciones_zona": len(zr), "con_RSI2_abierto_%": round(solapa.mean() * 100, 1),
            "con_RSI2_abierto_y_mismo_sentido_%": round(mismo.mean() * 100, 1),
            "horas_con_2_posiciones_%_del_tiempo_de_zona": round(horas_zr[solapa].sum() / horas_zr.sum() * 100, 1),
            "neto_zona_cuando_solapa_$": round(zr.neto[solapa].mean(), 2), "neto_zona_sin_solape_$": round(zr.neto[~solapa].mean(), 2)}


def correlaciones(d: pd.DataFrame) -> dict:
    ambos = d[(d.zona != 0) & (d.rsi2 != 0)]
    sem = d.resample("W").sum()
    mes = d.resample("ME").sum()
    return {"diaria_todos_los_dias": round(d.zona.corr(d.rsi2), 3),
            "diaria_dias_con_ambas": round(ambos.zona.corr(ambos.rsi2), 3) if len(ambos) > 10 else np.nan,
            "dias_con_ambas": len(ambos), "semanal": round(sem.zona.corr(sem.rsi2), 3), "mensual": round(mes.zona.corr(mes.rsi2), 3),
            "dias_ambas_pierden": int(((d.zona < 0) & (d.rsi2 < 0)).sum()),
            "p5_dia_conjunto_1+1_$": round((d.zona + d.rsi2).quantile(0.05), 0),
            "peor_dia_conjunto_1+1_$": round((d.zona + d.rsi2).min(), 0)}


def pesos(d: pd.DataFrame, corte: pd.Timestamp, relacion: tuple[float, float]) -> tuple[float, float]:
    """Pesos con presupuesto de riesgo `relacion` (zona:RSI) usando la volatilidad diaria de DESARROLLO, reescalados
    para que la volatilidad diaria de la cartera (en desarrollo) iguale a la de la zona de ruido sola."""
    dev = d[d.index < corte]
    sz, sr = dev.zona.std(), dev.rsi2.std()
    wz, wr = relacion[0] / sz, relacion[1] / sr
    s = (wz * dev.zona + wr * dev.rsi2).std()
    k = sz / s
    return round(wz * k, 3), round(wr * k, 3)


def evaluar_cartera(d: pd.DataFrame, wz: float, wr: float, capital: float) -> dict:
    p = wz * d.zona + wr * d.rsi2
    eq = capital + p.cumsum()
    dd = eq - np.maximum.accumulate(np.r_[capital, eq.to_numpy()])[1:]
    mes = p.resample("ME").sum()
    anual = p.groupby(p.index.year).sum()
    return {"pesos (zona, rsi2)": (wz, wr), "neto_$": round(p.sum(), 0), "volatilidad_diaria_$": round(p.std(), 1),
            "sharpe_anual": round(p.mean() / p.std() * np.sqrt(252), 2), "max_dd_$": round(dd.min(), 0),
            "max_dd_%_capital": round(dd.min() / capital * 100, 1), "peor_dia_$": round(p.min(), 0),
            "meses_positivos_%": round((mes > 0).mean() * 100, 1), "años_positivos": f"{(anual > 0).sum()}/{len(anual)}",
            "neto/|max_dd|": round(p.sum() / -dd.min(), 2) if dd.min() < 0 else np.inf}


def simular_riesgo(p: pd.Series, capital: float, limite_dia: float, caida_max: float, bloque: int, n: int,
                   horizonte: int, semilla: int) -> dict:
    """Bootstrap por bloques del P&L diario de la cartera en horizontes de `horizonte` sesiones. La detención por caída
    se aplica (tras dispararse, P&L = 0). El límite diario solo se CUENTA (sus efectos intradía no se pueden simular
    con P&L diario). Suposición: el pasado reciente se parece al futuro — no es una predicción."""
    x = p.to_numpy(float)
    m = len(x)
    rng = np.random.default_rng(semilla)
    k = int(np.ceil(horizonte / bloque))
    x2 = np.r_[x, x[:bloque]]
    finales, dds, dias_lim, detenida = np.empty(n), np.empty(n), np.empty(n), np.zeros(n, bool)
    for i in range(n):
        ini = rng.integers(0, m, k)
        s = np.concatenate([x2[j:j + bloque] for j in ini])[:horizonte]
        dias_lim[i] = (s <= -limite_dia).sum()
        eq = np.cumsum(s)
        dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
        golpe = np.flatnonzero(dd <= -caida_max)
        if len(golpe):
            detenida[i] = True
            eq = np.r_[eq[:golpe[0] + 1], np.full(horizonte - golpe[0] - 1, eq[golpe[0]])]
            dd = eq - np.maximum.accumulate(np.r_[0, eq])[1:]
        finales[i], dds[i] = eq[-1], dd.min()
    return {"P&L_anual_p5_$": round(np.percentile(finales, 5), 0), "P&L_anual_p50_$": round(np.percentile(finales, 50), 0),
            "P&L_anual_p95_$": round(np.percentile(finales, 95), 0), "prob_año_negativo_%": round((finales < 0).mean() * 100, 1),
            "max_dd_p50_$": round(np.percentile(dds, 50), 0), "max_dd_p95_$": round(np.percentile(dds, 5), 0),
            "max_dd_p95_%_capital": round(np.percentile(dds, 5) / capital * 100, 1),
            "prob_detencion_por_caida_%": round(detenida.mean() * 100, 1),
            "dias_al_año_sobre_limite_diario_media": round(dias_lim.mean(), 2),
            "prob_al_menos_1_dia_sobre_limite_%": round((dias_lim > 0).mean() * 100, 1)}
