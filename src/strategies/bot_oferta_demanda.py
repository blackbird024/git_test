"""Simulación del bot de oferta/demanda del usuario (reglas: edges/bot_oferta_demanda_oro.md).

Señales: `bot_oferta_demanda_senal.find_signal`, copiada literalmente del bot, sobre las últimas 259 velas de 1 h
cerradas (lo mismo que ve el bot en vivo: 260 velas menos la que se está formando).
Ejecución: a mercado en la apertura de la vela siguiente; stop y objetivo fijos (los del bot), resueltos minuto a
minuto; si el stop y el objetivo caen en el mismo minuto, stop. Máximo 2 posiciones; freno diario del 5 % (UTC).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.strategies.bot_oferta_demanda_senal import find_signal

VENTANA = 259          # velas cerradas que ve el bot (copy_rates_from_pos de 260 menos la que se forma)


@dataclass(frozen=True)
class Config:
    riesgo_pct: float = 0.5
    max_posiciones: int = 2
    freno_diario_pct: float = 5.0
    spread: float = 0.15            # $ por onza (XAUUSD Razor aprox.)
    comision_oz_lado: float = 0.035  # 7 $ por lote (100 oz) ida y vuelta
    deslizamiento: float = 0.05      # $ en entradas a mercado y stops
    capital: float = 50_000.0
    max_oz: int = 100_000


def ajustar_continuo(m1: pd.DataFrame) -> pd.DataFrame:
    """Ajuste aditivo hacia atrás: en cada cambio de instrument_id, el salto (apertura del nuevo - cierre del
    anterior) se resta de todo lo anterior. Aproxima un precio sin vencimientos (como el CFD)."""
    x = m1.copy()
    cambio = x.instrument_id.ne(x.instrument_id.shift()) & x.instrument_id.shift().notna()
    salto = np.where(cambio, x.open - x.close.shift(), 0.0)
    ajuste = salto[::-1].cumsum()[::-1] - salto          # suma de los saltos POSTERIORES a cada fila
    for c in ("open", "high", "low", "close"):
        x[c] = x[c] + ajuste
    return x


def velas_1h(m1: pd.DataFrame) -> pd.DataFrame:
    h = m1.resample("1h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last",
                                                             "volume": "sum"}).dropna()
    return h


def _salida(t_ini: int, d: int, sl: float, tp: float, hi: np.ndarray, lo: np.ndarray, media_spread: float):
    """Primer minuto (desde t_ini) en que salta el stop o el objetivo. Precios de la serie = medios; el stop de un
    largo salta con el bid (medio - spread/2), el objetivo cuando el bid llega al nivel."""
    paso = 20_000
    i = t_ini
    n = len(hi)
    while i < n:
        h, l = hi[i:i + paso], lo[i:i + paso]
        if d == 1:
            stop = l - media_spread <= sl
            obj = h - media_spread >= tp
        else:
            stop = h + media_spread >= sl
            obj = l + media_spread <= tp
        cual = stop | obj
        if cual.any():
            k = int(np.argmax(cual))
            return i + k, "stop" if stop[k] else "target"      # stop primero si coinciden
        i += paso
    return None, "fin_de_datos"


def backtest(m1: pd.DataFrame, cfg: Config = Config(), desde=None, hasta=None, progreso: bool = False) -> pd.DataFrame:
    m1 = m1.copy()
    m1.index = m1.index.tz_convert("UTC").tz_localize(None)       # todo en UTC sin zona
    h1 = velas_1h(m1)
    t1 = m1.index.to_numpy()
    op1, hi1, lo1, cl1 = (m1[c].to_numpy() for c in ("open", "high", "low", "close"))
    hs = cfg.spread / 2
    idx_h = h1.index
    # posición en los minutos del inicio de cada vela de 1 h
    pos_min = np.searchsorted(t1, idx_h.to_numpy())
    balance = cfg.capital
    abiertas, ops = [], []                     # abiertas: dicts con salida ya calculada
    dia, bal_dia = None, balance
    ini = VENTANA - 1
    for i in range(ini, len(h1) - 1):
        t_senal_fin = idx_h[i] + pd.Timedelta(hours=1)
        j = i + 1                              # vela de ejecución
        t_ej = idx_h[j]
        # realizar las salidas ocurridas antes de la apertura de la vela j
        for p in [p for p in abiertas if p["t_salida"] <= t_ej]:
            balance += p["neto"]
            ops.append(p)
            abiertas.remove(p)
        if desde is not None and t_ej < pd.Timestamp(desde):
            continue
        if hasta is not None and t_ej > pd.Timestamp(hasta) + pd.Timedelta(days=1):
            break
        hoy = t_ej.date()
        if hoy != dia:
            dia, bal_dia = hoy, balance
        if len(abiertas) >= cfg.max_posiciones:
            continue
        if (bal_dia - balance) / bal_dia * 100 >= cfg.freno_diario_pct:
            continue
        s = find_signal(h1.iloc[i - VENTANA + 1:i + 1].reset_index().rename(columns={"ts_event": "date", "index": "date"}))
        if s is None:
            continue
        direc, sl, tp, _ = s
        d = 1 if direc == "BUY" else -1
        k0 = pos_min[j]
        if k0 >= len(t1):
            break
        fill = op1[k0] + d * (hs + cfg.deslizamiento)
        if (fill - sl) * d <= 0 or (tp - fill) * d <= 0:
            continue                           # el broker rechazaría stops inválidos
        dist = abs(fill - sl)
        oz = int(min(cfg.max_oz, np.floor(balance * cfg.riesgo_pct / 100 / dist)))
        if oz < 1:
            continue
        k_s, motivo = _salida(k0, d, sl, tp, hi1, lo1, hs)
        if k_s is None:
            k_s = len(t1) - 1
            px = cl1[k_s] - d * hs
        elif motivo == "stop":
            abre_mas_alla = (op1[k_s] - hs <= sl) if d == 1 else (op1[k_s] + hs >= sl)
            base = (op1[k_s] - d * hs) if abre_mas_alla else sl
            px = base - d * cfg.deslizamiento
        else:
            px = tp
        bruto = (px - fill) * d * oz
        neto = bruto - 2 * cfg.comision_oz_lado * oz
        ops_bruto_sin_costes = ((sl if motivo == "stop" else px) - op1[k0]) * d * oz
        abiertas.append({"direction": d, "oz": oz, "t_senal": t_senal_fin, "entry_time": t1[k0], "entry": fill,
                         "sl": sl, "tp": tp, "t_salida": pd.Timestamp(t1[k_s]),
                         "exit_price": px, "motivo": motivo, "bruto_sin_costes": ops_bruto_sin_costes, "neto": neto,
                         "riesgo_usd": dist * oz, "r": neto / (dist * oz), "horas": (k_s - k0) / 60})
        if progreso and len(ops) % 200 == 0 and ops:
            print(f"  {t_ej.date()} operaciones cerradas: {len(ops)}", flush=True)
    for p in abiertas:
        balance += p["neto"]
        ops.append(p)
    return pd.DataFrame(ops).sort_values("entry_time").reset_index(drop=True) if ops else pd.DataFrame()
