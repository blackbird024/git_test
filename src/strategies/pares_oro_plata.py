"""PARES_ORO_PLATA_v1.0: reversión del ratio oro/plata (reglas en edges/pares_oro_plata.md).

Solo simula con velas diarias ya cerradas; nunca ejecuta órdenes.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

VERSION = "PARES_ORO_PLATA_v1.0"


@dataclass(frozen=True)
class Config:
    ventana: int = 60
    umbral: float = 2.0
    max_sesiones: int = 20
    onzas_oro: float = 10.0          # MGC
    onzas_plata: float = 1000.0      # SIL
    tick_oro: float = 0.10
    tick_plata: float = 0.005
    comision_lado: float = 1.0       # $ por contrato y lado
    ticks_desliz: int = 1            # por pata y lado

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)


def preparar(oro: pd.DataFrame, plata: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Une las dos series diarias ajustadas (salida de `sesiones_diarias_databento`) y calcula z."""
    cols = ["open", "close", "open_aj", "close_aj"]
    d = oro[cols].add_suffix("_o").join(plata[cols].add_suffix("_p"), how="inner")
    d = d[d.index.dayofweek < 5]
    x = np.log(d.close_aj_o) - np.log(d.close_aj_p)
    d["z"] = (x - x.rolling(cfg.ventana).mean()) / x.rolling(cfg.ventana).std()
    return d


def backtest(d: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Una posición a la vez. dir_oro = -1 (corto oro + largo plata) si z > umbral; +1 si z < -umbral."""
    z = d.z.to_numpy()
    n, i, ops = len(d), 0, []
    coste = 2 * 2 * cfg.comision_lado + 2 * cfg.ticks_desliz * (cfg.tick_oro * cfg.onzas_oro + cfg.tick_plata * cfg.onzas_plata)
    while i < n - 1:
        if not np.isfinite(z[i]) or abs(z[i]) <= cfg.umbral:
            i += 1
            continue
        d_oro = -1 if z[i] > cfg.umbral else 1
        e = i + 1                                                   # entrada en la apertura siguiente
        k = e
        while k < n - 1:
            vuelve = (z[k] <= 0) if d_oro == -1 else (z[k] >= 0)
            if vuelve or k - e + 1 >= cfg.max_sesiones:
                break
            k += 1
        x = min(k + 1, n - 1)                                       # salida en la apertura siguiente
        motivo = "z_cero" if ((z[k] <= 0) if d_oro == -1 else (z[k] >= 0)) else ("tiempo" if k + 1 < n else "fin")
        pata_o = d_oro * d.open_o.iloc[e] * cfg.onzas_oro * (d.open_aj_o.iloc[x] / d.open_aj_o.iloc[e] - 1)
        pata_p = -d_oro * d.open_p.iloc[e] * cfg.onzas_plata * (d.open_aj_p.iloc[x] / d.open_aj_p.iloc[e] - 1)
        bruto = pata_o + pata_p
        ops.append({"t_senal": d.index[i], "t_entrada": d.index[e], "t_salida": d.index[x], "dir_oro": d_oro,
                    "z_senal": round(z[i], 2), "sesiones": x - e, "pata_oro": pata_o, "pata_plata": pata_p,
                    "bruto": bruto, "neto": bruto - coste, "motivo": motivo,
                    "nominal_oro": d.open_o.iloc[e] * cfg.onzas_oro, "nominal_plata": d.open_p.iloc[e] * cfg.onzas_plata})
        i = x if x > i else i + 1                                   # nueva señal posible desde el día de salida
    return pd.DataFrame(ops)
