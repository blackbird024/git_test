"""RSI2_SURVIVOR_V1 y NOISE_ZONE_SURVIVOR_V1: versiones CONGELADAS de las dos supervivientes.

No reimplementan nada: llaman al código original (src/strategies/nq_rsi2.py y src/strategies/zona_ruido.py) con sus
parámetros originales y comprueban que los archivos fuente no han cambiado (SHA-256). Cualquier cambio en el código
original hace fallar `comprobar_integridad()` y las pruebas.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.engine.costes import Costes
from src.strategies import nq_rsi2, zona_ruido as z

RAIZ = Path(__file__).resolve().parents[2]
SHA256 = {
    "src/strategies/nq_rsi2.py": "24716d144f90d0db2e9f0b49e1ed90bffda4774ea4d15ff9afccbd7eb315c898",
    "src/strategies/zona_ruido.py": "a00839d165030e57fe5c54476aabd6439db57cacccfc59b73545d8527d052cdb",
    "src/engine/costes.py": "d33f84d08cb9a4c9009f14922d9bf70a80eec2e9dff29614b434473d062b8007",
    "src/data/datos.py": "bd1028b5b50b3062d40ff6fb30acb8f85103c57f2c5be25ffe94540e338b5108",
}
RSI2_SURVIVOR_V1 = nq_rsi2.Config()             # entrada 20, salida 70, 5 sesiones, SMA200, RSI(2), 1 MNQ, Costes()
NOISE_ZONE_SURVIVOR_V1 = z.Config()             # 14 días, mult 1,0, chequeos 10:00-15:30 cada 30 min, 1 tick + 1 $/lado
AUDITORIA = RAIZ / "auditoria" / "experimentos" / "20260930_0633"


def comprobar_integridad() -> dict:
    out = {}
    for ruta, esperado in SHA256.items():
        real = hashlib.sha256((RAIZ / ruta).read_bytes()).hexdigest()
        out[ruta] = real == esperado
    if not all(out.values()):
        raise RuntimeError(f"El código de una superviviente ha cambiado: {out}")
    return out


def utc(o: pd.DataFrame) -> pd.DataFrame:
    o = o.copy()
    o["t_entrada"] = pd.to_datetime(o.t_entrada, utc=True)
    o["t_salida"] = pd.to_datetime(o.t_salida, utc=True)
    return o


def rsi2(m1: pd.DataFrame, excluir: frozenset, cfg: nq_rsi2.Config = RSI2_SURVIVOR_V1) -> pd.DataFrame:
    o = utc(nq_rsi2.backtest(m1, cfg, excluir))
    o["direccion"] = 1
    return o


def zona_ruido(m1: pd.DataFrame, excluir: frozenset, cfg: z.Config = NOISE_ZONE_SURVIVOR_V1) -> pd.DataFrame:
    o, _ = z.backtest(m1, cfg, excluir)
    return utc(o)


def costes_rsi2(mult: float = 1.0, ticks_extra: int = 0) -> Costes:
    return Costes(ticks_normal=1 + ticks_extra, ticks_apertura=2 + ticks_extra, multiplicador=mult)


def cfg_zr_costes(mult: float = 1.0, ticks_extra: int = 0) -> z.Config:
    return NOISE_ZONE_SURVIVOR_V1.con(ticks_entrada=(1 + ticks_extra) * mult, ticks_salida=(1 + ticks_extra) * mult,
                                      comision_lado=1.0 * mult)
