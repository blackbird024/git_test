"""Pruebas de aleatorización (PRE-REGISTRO §5). Cada réplica mantiene días, horas y número de operaciones y elimina la
señal específica. p = proporción de réplicas con expectativa neta >= la real (unilateral)."""
from __future__ import annotations

import numpy as np
import pandas as pd

TICK, PV, COM = 0.25, 2.0, 2.0


def _resumen(real: float, sims: np.ndarray) -> dict:
    return {"expectativa_real_$": round(real, 2), "media_aleatoria_$": round(float(sims.mean()), 2),
            "p5_aleatoria_$": round(float(np.percentile(sims, 5)), 2), "p95_aleatoria_$": round(float(np.percentile(sims, 95)), 2),
            "p_valor": round(float((sims >= real).mean()), 4), "replicas": len(sims)}


def zr_direccion(ops: pd.DataFrame, n: int, semilla: int) -> dict:
    """ZR-N1: mismas entradas y salidas, sentido aleatorio. Precios sin deslizamiento reconstruidos y costes iguales."""
    d = ops.direccion.to_numpy()
    raw_e = ops.entrada.to_numpy() - d * TICK
    raw_x = ops.salida.to_numpy() + d * TICK
    rng = np.random.default_rng(semilla)
    s = rng.choice([-1, 1], size=(n, len(ops)))
    neto = (s * (raw_x - raw_e) - 2 * TICK) * PV - COM
    return _resumen(ops.neto.mean(), neto.mean(axis=1))


def zr_momento(ctx, ops: pd.DataFrame, n: int, semilla: int, chequeos=range(30, 361, 30)) -> dict:
    """ZR-N2: mismos días y nº de operaciones por día; entrada en un chequeo aleatorio, sentido aleatorio, duración de
    una operación real al azar (salida como máximo en la apertura de 15:59)."""
    rth = np.flatnonzero(ctx.rth)
    fechas = ctx.fecha[rth]
    minuto = ctx.min_ny[rth] - 570
    df = pd.DataFrame({"f": fechas, "m": minuto, "o": ctx.O[rth]})
    grid = df.pivot_table(index="f", columns="m", values="o").ffill(axis=1)
    dias = pd.DatetimeIndex(pd.to_datetime(ops.t_entrada, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()).to_numpy().astype("datetime64[D]")
    fila = grid.index.get_indexer(dias)
    O = grid.to_numpy()
    dur = ((ops.t_salida - ops.t_entrada).dt.total_seconds() / 60).round().astype(int).to_numpy()
    rng = np.random.default_rng(semilla)
    ch = np.array(list(chequeos))
    sims = np.empty(n)
    for k in range(n):
        m0 = rng.choice(ch, len(ops))
        m1 = np.minimum(m0 + rng.choice(dur, len(ops)), O.shape[1] - 1)
        s = rng.choice([-1, 1], len(ops))
        px0, px1 = O[fila, m0], O[fila, m1]
        neto = (s * (px1 - px0) - 2 * TICK) * PV - COM
        sims[k] = np.nanmean(neto)
    return _resumen(ops.neto.mean(), sims)


def rsi2_dias(ops: pd.DataFrame, s: pd.DataFrame, n: int, semilla: int, filtro_sma: bool, excluir) -> dict:
    """RSI2-N1/N2: entradas en sesiones al azar (con o sin cierre > SMA200 la víspera), duración de una operación real al
    azar, mismos costes (2 ticks en la entrada y 2 en la salida por ser reaperturas de Globex, 1 $/lado)."""
    oa, o = s.open_aj.to_numpy(), s.open.to_numpy()
    ok = np.ones(len(s), bool)
    ok[0] = False
    if filtro_sma:
        ok[1:] &= (s.close_aj > s.sma).to_numpy()[:-1]
    ok &= ~np.isin(s.index.date, list(excluir))
    ok[-6:] = False
    cand = np.flatnonzero(ok)
    dur = ops.sesiones.to_numpy()
    rng = np.random.default_rng(semilla)
    sims = np.empty(n)
    for k in range(n):
        e = rng.choice(cand, len(ops))
        x = np.minimum(e + rng.choice(dur, len(ops)), len(s) - 1)
        ret = oa[x] / oa[e] - 1
        neto = (o[e] * ret - 4 * TICK) * PV - COM
        sims[k] = neto.mean()
    return _resumen(ops.neto.mean(), sims)
