"""Cruce de medias móviles exponenciales (o MACD) con filtro de rango (ADX) opcional.

Tipos de señal (`signal_mode`):
  "ema":         la EMA rápida cruza la lenta.
  "macd_signal": la línea MACD (EMA rápida - EMA lenta) cruza su línea de señal (EMA de `macd_signal` periodos).
  "macd_zero":   la línea MACD cruza el cero (equivale al cruce de las EMA rápida y lenta).

Reglas (config/ma_mnq.yaml, config/ma_mgc.yaml):
  - EMA rápida y lenta sobre los cierres de 5 min de la sesión regular (continuas entre días).
  - Señal al CIERRE de la vela en que la rápida cruza a la lenta (arriba = largo, abajo = corto),
    solo entre `primera_senal` y `ultima_senal` y solo si ADX(14) >= umbral (si hay filtro).
  - Entrada en la apertura de la vela siguiente, con deslizamiento.
  - Salida: el primer evento de (a) stop de emergencia a k x ATR diario, (b) cruce contrario
    (salida a mercado en la apertura siguiente) o (c) cierre a las 15:45.
  - Tras salir por cruce contrario, ese mismo cruce puede abrir la posición opuesta si pasa el filtro.
  - Una sola posición a la vez y como máximo `max_operaciones_dia` entradas al día.

El ADX mide la FUERZA de la tendencia sin importar su dirección: valores bajos (< 20) indican
mercado lateral, en rango. Es el filtro clásico para no operar cruces en rango.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.strategies.orb_5m import DayResult, _simulate, to_bars

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class MAConfig:
    symbol: str = "MNQ"
    point_value: float = 2.0
    tick: float = 0.25
    bar_minutes: int = 5
    first_signal: str = "10:00"
    last_signal: str = "15:00"
    time_exit: str = "15:45"
    fast: int = 9
    slow: int = 21
    signal_mode: str = "ema"
    macd_signal: int = 9
    adx_period: int = 14
    adx_min: float | None = 20
    stop_atr: float = 0.25
    max_trades_day: int = 3
    risk_usd: float = 250.0
    max_contracts: int = 10
    fixed_contracts: int | None = None
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 1
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path) -> "MAConfig":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        return cls(
            symbol=c["instrumento"]["simbolo"], point_value=c["instrumento"]["valor_punto_usd"],
            tick=c["instrumento"]["tick"], bar_minutes=c["velas_minutos"],
            first_signal=c["horario_et"]["primera_senal"], last_signal=c["horario_et"]["ultima_senal"],
            time_exit=c["horario_et"]["salida_tiempo"], fast=c["ema_rapida"], slow=c["ema_lenta"],
            signal_mode=c.get("tipo_senal", "ema"), macd_signal=c.get("senal_macd", 9),
            adx_period=c["adx_periodo"], adx_min=c["adx_minimo"], stop_atr=c["stop_atr"],
            max_trades_day=c["max_operaciones_dia"], risk_usd=c["riesgo"]["riesgo_por_operacion_usd"],
            max_contracts=c["riesgo"]["contratos_max"], fixed_contracts=c["riesgo"]["contratos_fijos"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "MAConfig":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        filt = "sinFiltro" if self.adx_min is None else f"ADX{self.adx_min:g}"
        size = f"{self.fixed_contracts}contrato_fijo" if self.fixed_contracts else f"{self.risk_usd:g}$"
        if self.signal_mode == "ema":
            return f"MA_{self.symbol}_{self.fast}-{self.slow}_{filt}_{size}"
        kind = "senal" if self.signal_mode == "macd_signal" else "cero"
        return f"MACD_{self.symbol}_{self.bar_minutes}m_{kind}_{filt}_{size}"


# ------------------------------------------------------------------------------ indicadores
def adx(df: pd.DataFrame, n: int) -> pd.Series:
    """ADX de Wilder: suavizado exponencial con alfa = 1/n de +DM, -DM y rango verdadero."""
    up, down = df.high.diff(), -df.low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    prev_close = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - prev_close).abs(), (df.low - prev_close).abs()], axis=1).max(axis=1)
    a = 1 / n
    atr = tr.ewm(alpha=a, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=a, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=a, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False).mean()


def add_signals(bars: pd.DataFrame, cfg: MAConfig) -> pd.DataFrame:
    """Añade columnas cross (+1 cruce al alza, -1 a la baja, 0 nada) y ok_filter a las velas."""
    out = bars.copy()
    fast = out.close.ewm(span=cfg.fast, adjust=False).mean()
    slow = out.close.ewm(span=cfg.slow, adjust=False).mean()
    macd = fast - slow
    if cfg.signal_mode == "macd_signal":
        above = np.sign(macd - macd.ewm(span=cfg.macd_signal, adjust=False).mean())
    else:  # "ema" y "macd_zero" son el mismo cruce
        above = np.sign(macd)
    out["cross"] = np.where((above > 0) & (above.shift() <= 0), 1, np.where((above < 0) & (above.shift() >= 0), -1, 0))
    out["adx"] = adx(out, cfg.adx_period)
    out["ok_filter"] = True if cfg.adx_min is None else (out.adx >= cfg.adx_min)
    return out


# -------------------------------------------------------------------------------- backtest
def backtest(minutes: pd.DataFrame, atr: pd.Series, cfg: MAConfig):
    bars = add_signals(to_bars(minutes, cfg.bar_minutes), cfg)
    trades, days, paths = [], [], []
    for date, day in bars.groupby(bars.index.date):
        res = _run_day(date, day, atr.get(date), cfg)
        days.append({"date": pd.Timestamp(date), "status": res[0] if res else "sin_senal"})
        for trade, path in res[1:] if res else []:
            trades.append(trade)
            paths.append(path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def _run_day(date, day: pd.DataFrame, atr, cfg: MAConfig):
    """Devuelve [estado, (trade, recorrido), (trade, recorrido), ...]."""
    if atr is None or np.isnan(atr):
        return ["sin_atr"]
    tz = day.index.tz
    ts = lambda hhmm: pd.Timestamp(f"{date} {hhmm}", tz=tz)  # noqa: E731
    idx = day.index
    t_first, t_last, t_exit = ts(cfg.first_signal), ts(cfg.last_signal), ts(cfg.time_exit)
    cross, ok = day.cross.to_numpy(), day.ok_filter.to_numpy()
    in_window = (idx >= t_first) & (idx < t_last)
    results, status, start = ["sin_senal"], "sin_senal", 0
    while len(results) - 1 < cfg.max_trades_day:
        cand = [i for i in range(start, len(day) - 1) if in_window[i] and cross[i] != 0]
        sig = [i for i in cand if ok[i]]
        if cand and not sig:
            status = "cruces_en_rango_filtrados"
        if not sig:
            break
        s = sig[0]
        e, d = s + 1, int(cross[s])
        rev = [c for c in range(e, len(day) - 1) if cross[c] == -d]
        exit_ts = idx[rev[0] + 1] if rev and idx[rev[0] + 1] < t_exit else t_exit
        entry = day.open.iloc[e] + d * cfg.slip_entry * cfg.tick
        stop = entry - d * cfg.stop_atr * atr
        dist = cfg.stop_atr * atr
        if cfg.fixed_contracts:
            qty = cfg.fixed_contracts
        else:
            qty = min(int(np.floor(cfg.risk_usd / (dist * cfg.point_value) + 1e-9)), cfg.max_contracts)
            if qty < 1:
                status = "riesgo_de_1_contrato_excede_limite"
                break
        px, t_out, reason, path = _simulate(day.iloc[e:], d, entry, stop, None, qty, exit_ts, cfg)
        if reason == "tiempo" and rev and t_out == exit_ts < t_exit:
            reason = "cruce_contrario"
        comm = 2 * cfg.commission_side * qty
        gross = (px - entry) * d * cfg.point_value * qty
        results.append(({"date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": idx[e],
                         "entry": entry, "stop": stop, "target": None, "exit_time": t_out, "exit": px,
                         "exit_reason": reason, "risk_usd": dist * cfg.point_value * qty,
                         "gross": gross, "commission": comm, "pnl": gross - comm}, path))
        status = "operada"
        if t_out >= t_exit or reason == "tiempo":   # cierre de las 15:45 o fin de datos del día
            break
        # Siguiente búsqueda: desde la vela del cruce contrario (puede girar la posición) o del stop.
        start = rev[0] if reason == "cruce_contrario" else int(np.searchsorted(idx, t_out))
    results[0] = status
    return results
