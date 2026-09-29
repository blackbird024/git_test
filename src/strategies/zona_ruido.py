"""ZONA_RUIDO_MNQ_v1.0: momentum intradía con "zona de ruido" (Zarattini, Aziz y Barbon, 2024, "Beat the Market").

Misma regla que archive/src/strategies/noise_area.py (versión "como el estudio", 1 MNQ fijo), portada al marco actual
(datos en UTC, horas de Nueva York con zona horaria). Reglas en edges/zona_ruido_mnq.md.

  - sigma(m): media, en los 14 días anteriores, de |cierre(m) / apertura del día - 1| en el minuto m de la sesión.
  - Banda superior(m) = max(apertura, cierre anterior) x (1 + sigma(m)); inferior = min(...) x (1 - sigma(m)).
  - Solo se decide a las HH:00 y HH:30, de 10:00 a 15:30 NY, con el cierre del minuto anterior; se ejecuta en la
    apertura del minuto del chequeo (con deslizamiento).
      sin posición: por encima de la banda superior -> largo; por debajo de la inferior -> corto.
      largo: sale si el precio < max(banda superior, VWAP); si además está bajo la banda inferior, gira a corto.
      corto: simétrico con min(banda inferior, VWAP).
  - Todo se cierra al final de la sesión (cierre de la vela de 15:59).
Solo genera señales y simula; nunca ejecuta órdenes.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from src.horas import NUEVA_YORK

VERSION = "ZONA_RUIDO_MNQ_v1.0"


@dataclass(frozen=True)
class Config:
    version: str = VERSION
    primer_chequeo: int = 30         # minutos desde las 9:30 NY (30 = 10:00)
    ultimo_chequeo: int = 360        # 360 = 15:30
    cada: int = 30
    dias_ruido: int = 14
    mult: float = 1.0
    contratos: int = 1
    valor_punto: float = 2.0
    tick: float = 0.25
    comision_lado: float = 1.0
    ticks_entrada: int = 1
    ticks_salida: int = 1

    def con(self, **cambios) -> "Config":
        return replace(self, **cambios)

    @property
    def chequeos(self) -> list[int]:
        return list(range(self.primer_chequeo, self.ultimo_chequeo + 1, self.cada))


def preparar(m1: pd.DataFrame, cfg: Config):
    """Sesión regular (09:30-16:00 NY) con el minuto de la sesión; por día: apertura, cierre anterior (sin hueco en
    los días de cambio de contrato) y sigma por minuto calculada SOLO con días anteriores."""
    ny = m1.tz_convert(NUEVA_YORK)
    rth = ny.between_time("09:30", "16:00", inclusive="left").copy()
    rth["date"] = rth.index.date
    rth["minute"] = (rth.index.hour - 9) * 60 + rth.index.minute - 30
    g = rth.groupby("date")
    daily = pd.DataFrame({"open": g.open.first(), "close": g.close.last(),
                          "first_id": g.instrument_id.first(), "last_id": g.instrument_id.last()})
    mismo = daily.first_id == daily.last_id.shift()
    daily["prev_close"] = daily.close.shift().where(mismo, daily.open)
    rth["move"] = (rth.close / rth.date.map(daily.open) - 1).abs()
    grid = rth.pivot_table(index="date", columns="minute", values="move")
    sigma = grid.rolling(cfg.dias_ruido, min_periods=10).mean().shift()
    return rth, daily, sigma


def operar_dia(fecha, dia: pd.DataFrame, apertura, cierre_ant, sigma_fila: pd.Series, cfg: Config):
    """Simula un día. Devuelve la lista de operaciones (dict)."""
    O, H, L, C = (dia[c].to_numpy() for c in ("open", "high", "low", "close"))
    M = dia.minute.to_numpy()
    tipico = (dia.high + dia.low + dia.close) / 3
    vwap = ((tipico * dia.volume).cumsum() / dia.volume.cumsum().replace(0, np.nan)).to_numpy()
    sig = sigma_fila.reindex(M).to_numpy()
    sup = max(apertura, cierre_ant) * (1 + cfg.mult * sig)
    inf = min(apertura, cierre_ant) * (1 - cfg.mult * sig)
    pv, c_lado, tick = cfg.valor_punto * cfg.contratos, cfg.comision_lado * cfg.contratos, cfg.tick
    chequeos = set(cfg.chequeos)
    out, pos = [], None

    def cerrar(p, i, px, motivo):
        bruto = (px - p["entrada"]) * p["d"] * pv
        out.append({"fecha": fecha, "direccion": p["d"], "contratos": cfg.contratos, "t_entrada": dia.index[p["i"]],
                    "entrada": p["entrada"], "t_salida": dia.index[i], "salida": px, "motivo": motivo,
                    "bruto": bruto, "comision": 2 * c_lado, "neto": bruto - 2 * c_lado,
                    "banda_sup_entrada": p["sup"], "banda_inf_entrada": p["inf"]})

    for i in range(1, len(dia)):
        if M[i] in chequeos and not np.isnan(sig[i - 1]):
            p_, up, lo, vw = C[i - 1], sup[i - 1], inf[i - 1], vwap[i - 1]
            if pos is not None:
                trail = max(up, vw) if pos["d"] == 1 else min(lo, vw)
                if (pos["d"] == 1 and p_ < trail) or (pos["d"] == -1 and p_ > trail):
                    cerrar(pos, i, O[i] - pos["d"] * cfg.ticks_salida * tick, "trailing")
                    pos = None
            if pos is None:
                if p_ > up:
                    pos = {"d": 1, "entrada": O[i] + cfg.ticks_entrada * tick, "i": i, "sup": up, "inf": lo}
                elif p_ < lo:
                    pos = {"d": -1, "entrada": O[i] - cfg.ticks_entrada * tick, "i": i, "sup": up, "inf": lo}
    if pos is not None:
        cerrar(pos, len(dia) - 1, C[-1] - pos["d"] * cfg.ticks_salida * tick, "cierre")
    return out


def backtest(m1: pd.DataFrame, cfg: Config = Config(), excluir: frozenset = frozenset()):
    """Devuelve (operaciones, días). `excluir`: sesiones ilíquidas previsibles (regla causal del proyecto)."""
    rth, daily, sigma = preparar(m1, cfg)
    ops, dias = [], []
    for fecha, dia in rth.groupby("date"):
        if fecha in excluir:
            dias.append({"fecha": fecha, "estado": "excluida"})
            continue
        d = daily.loc[fecha]
        if fecha not in sigma.index or sigma.loc[fecha].isna().all():
            dias.append({"fecha": fecha, "estado": "sin_historia"})
            continue
        r = operar_dia(fecha, dia, d.open, d.prev_close, sigma.loc[fecha], cfg)
        dias.append({"fecha": fecha, "estado": "operada" if r else "sin_senal", "operaciones": len(r)})
        ops.extend(r)
    return pd.DataFrame(ops), pd.DataFrame(dias)


def senales(m1: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Para la auditoría de look-ahead: instantes de entrada y dirección."""
    ops, _ = backtest(m1, cfg)
    if ops.empty:
        return pd.DataFrame({"t_senal": pd.Series(dtype="datetime64[ns, UTC]")})
    return pd.DataFrame({"t_senal": pd.DatetimeIndex(ops.t_entrada).tz_convert("UTC"), "direccion": ops.direccion,
                         "entrada": ops.entrada}).reset_index(drop=True)


def niveles(m1: pd.DataFrame, apertura: float | None = None, cfg: Config = Config()) -> dict:
    """Niveles para la PRÓXIMA sesión, con los datos hasta la última sesión regular completa.
    Devuelve cierre anterior, sigma de cada chequeo (se conoce la víspera) y, si se da la apertura de hoy
    (09:30 NY), las bandas superior e inferior de cada chequeo."""
    rth, daily, _ = preparar(m1, cfg)
    completos = [f for f, g in rth.groupby("date") if g.minute.max() >= 389]
    ultimo = completos[-1]
    rth = rth[rth.date <= ultimo]                                # una sesión en curso no cuenta
    grid = rth.pivot_table(index="date", columns="minute", values="move")
    # Misma cuenta que el backtest (media móvil de 14 días); la última fila es la sigma de la PRÓXIMA sesión
    sig = grid.rolling(cfg.dias_ruido, min_periods=10).mean().iloc[-1]
    cierre_ant = daily.loc[ultimo, "close"]
    filas = []
    for m in cfg.chequeos:
        s = sig.get(m - 1, np.nan)                               # el chequeo de las HH:MM usa la banda del minuto anterior
        fila = {"chequeo_min": m, "sigma_%": s * 100}
        if apertura is not None:
            fila["banda_sup"] = max(apertura, cierre_ant) * (1 + cfg.mult * s)
            fila["banda_inf"] = min(apertura, cierre_ant) * (1 - cfg.mult * s)
        filas.append(fila)
    return {"ultima_sesion": ultimo, "cierre_anterior": cierre_ant, "tabla": pd.DataFrame(filas)}
