"""Copia de `zona_ruido.operar_dia` con un único cambio configurable: `retardo` minutos entre la decisión y la
ejecución (prueba de latencia). Con retardo = 0 debe dar exactamente las mismas operaciones que el original
(comprobado en auditoria/tests). El original no se modifica."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategies import zona_ruido as z


def operar_dia(fecha, dia: pd.DataFrame, apertura, cierre_ant, sigma_fila: pd.Series, cfg: z.Config, retardo: int = 0):
    O, C = dia.open.to_numpy(), dia.close.to_numpy()
    M = dia.minute.to_numpy()
    tipico = (dia.high + dia.low + dia.close) / 3
    vwap = ((tipico * dia.volume).cumsum() / dia.volume.cumsum().replace(0, np.nan)).to_numpy()
    sig = sigma_fila.reindex(M).to_numpy()
    sup = max(apertura, cierre_ant) * (1 + cfg.mult * sig)
    inf = min(apertura, cierre_ant) * (1 - cfg.mult * sig)
    pv, c_lado, tick = cfg.valor_punto * cfg.contratos, cfg.comision_lado * cfg.contratos, cfg.tick
    chequeos = set(cfg.chequeos)
    out, pos = [], None
    n = len(dia)

    def cerrar(p, i, px, motivo, bruto_px):
        bruto = (px - p["entrada"]) * p["d"] * pv
        out.append({"fecha": fecha, "direccion": p["d"], "t_entrada": dia.index[p["i"]], "entrada": p["entrada"],
                    "t_salida": dia.index[i], "salida": px, "motivo": motivo, "bruto_sin_costes": (bruto_px - p["raw"]) * p["d"] * pv,
                    "bruto": bruto, "comision": 2 * c_lado, "neto": bruto - 2 * c_lado})

    for i in range(1, n):
        if M[i] in chequeos and not np.isnan(sig[i - 1]):
            j = min(i + retardo, n - 1)                      # vela de ejecución
            p_, up, lo, vw = C[i - 1], sup[i - 1], inf[i - 1], vwap[i - 1]
            if pos is not None:
                trail = max(up, vw) if pos["d"] == 1 else min(lo, vw)
                if (pos["d"] == 1 and p_ < trail) or (pos["d"] == -1 and p_ > trail):
                    cerrar(pos, j, O[j] - pos["d"] * cfg.ticks_salida * tick, "trailing", O[j])
                    pos = None
            if pos is None:
                if p_ > up:
                    pos = {"d": 1, "entrada": O[j] + cfg.ticks_entrada * tick, "raw": O[j], "i": j}
                elif p_ < lo:
                    pos = {"d": -1, "entrada": O[j] - cfg.ticks_entrada * tick, "raw": O[j], "i": j}
    if pos is not None:
        cerrar(pos, n - 1, C[-1] - pos["d"] * cfg.ticks_salida * tick, "cierre", C[-1])
    return out


def backtest(m1: pd.DataFrame, cfg: z.Config = z.Config(), excluir: frozenset = frozenset(), retardo: int = 0) -> pd.DataFrame:
    rth, daily, sigma = z.preparar(m1, cfg)
    ops = []
    for fecha, dia in rth.groupby("date"):
        if fecha in excluir or fecha not in sigma.index or sigma.loc[fecha].isna().all():
            continue
        d = daily.loc[fecha]
        ops.extend(operar_dia(fecha, dia, d.open, d.prev_close, sigma.loc[fecha], cfg, retardo))
    return pd.DataFrame(ops)
