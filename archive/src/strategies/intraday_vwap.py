"""Dos estrategias alrededor del VWAP, con la misma estructura de backtest que la ORB de 5 minutos
(misma simulación de operaciones y mismo recorrido para el drawdown trailing de Apex).

1) Reversión a la media (MRConfig, velas de 5 min, config/mean_reversion.yaml):
   Si una vela cierra a más de k x ATR del VWAP, se entra EN CONTRA en la apertura de la siguiente.
   Objetivo = VWAP en el momento de la señal. Stop a la misma distancia al otro lado (1:1).

2) Tendencia con VWAP (VTConfig, velas de 1 min, config/vwap_mgc.yaml):
   Tendencia alcista = cierre > VWAP y > apertura del día; entrada en el retroceso que toca el VWAP
   y cierra de nuevo del lado de la tendencia. Stop al otro lado del VWAP a k x ATR. Objetivo 2R.

En ambas: una operación al día como máximo, entrada en la apertura de la vela siguiente con
deslizamiento, salida por tiempo a las 15:45.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.strategies.orb_5m import DayResult, _simulate, to_bars

ROOT = Path(__file__).resolve().parent.parent.parent


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP acumulado desde la primera vela, con precio típico (máximo + mínimo + cierre) / 3."""
    typical = (df.high + df.low + df.close) / 3
    vol = df.volume.astype(float)
    return (typical * vol).cumsum() / vol.cumsum().replace(0, np.nan)


@dataclass(frozen=True)
class _Common:
    point_value: float = 2.0
    tick: float = 0.25
    first_signal: str = "10:30"
    last_signal: str = "15:00"
    time_exit: str = "15:45"
    atr_days: int = 14
    risk_usd: float = 150.0
    max_contracts: int = 10
    fixed_contracts: int | None = None
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 0
    slip_target: int = 0

    @staticmethod
    def _common_from(c: dict) -> dict:
        return dict(
            point_value=c["instrumento"]["valor_punto_usd"], tick=c["instrumento"]["tick"],
            first_signal=c["horario_et"]["primera_senal"], last_signal=c["horario_et"]["ultima_senal"],
            time_exit=c["horario_et"]["salida_tiempo"], atr_days=c["atr_dias"],
            risk_usd=c["riesgo"]["riesgo_por_operacion_usd"], max_contracts=c["riesgo"]["contratos_max"],
            fixed_contracts=c["riesgo"]["contratos_fijos"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes):
        return replace(self, **changes)

    def _size_label(self) -> str:
        return f"{self.fixed_contracts}contrato_fijo" if self.fixed_contracts else f"{self.risk_usd:g}$"

    def size(self, dist: float) -> int:
        """Contratos para una distancia al stop `dist` (puntos). 0 = no operar."""
        if self.fixed_contracts:
            return self.fixed_contracts
        qty = int(np.floor(self.risk_usd / (dist * self.point_value) + 1e-9))
        return min(qty, self.max_contracts) if qty >= 1 else 0


@dataclass(frozen=True)
class MRConfig(_Common):
    bar_minutes: int = 5
    deviation_atr: float = 0.5
    stop_ratio: float = 1.0

    @classmethod
    def from_yaml(cls, path="config/mean_reversion.yaml") -> "MRConfig":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        return cls(**cls._common_from(c), bar_minutes=c["velas_minutos"],
                   deviation_atr=c["desviacion_atr"], stop_ratio=c["relacion_stop_objetivo"])

    @property
    def label(self) -> str:
        return f"MR_desv{self.deviation_atr:g}ATR_{self._size_label()}"


@dataclass(frozen=True)
class VTConfig(_Common):
    stop_atr: float = 0.4
    target_r: float = 2.0

    @classmethod
    def from_yaml(cls, path="config/vwap_mgc.yaml") -> "VTConfig":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        return cls(**cls._common_from(c), stop_atr=c["stop_atr"], target_r=c["take_profit_r"])

    @property
    def label(self) -> str:
        return f"VWAP_MGC_stop{self.stop_atr:g}ATR_{self._size_label()}"


# ------------------------------------------------------------------------------ backtest
def backtest(minutes: pd.DataFrame, atr: pd.Series, cfg):
    """(trades, días, recorridos), igual que orb_5m.backtest."""
    bars = to_bars(minutes, cfg.bar_minutes) if isinstance(cfg, MRConfig) else \
        minutes.between_time("09:30", "16:00", inclusive="left")
    run_day = _run_mr_day if isinstance(cfg, MRConfig) else _run_vt_day
    trades, days, paths = [], [], []
    for date, day in bars.groupby(bars.index.date):
        res = run_day(date, day, atr.get(date), cfg)
        days.append({"date": pd.Timestamp(date), "status": res.status})
        if res.trade:
            trades.append(res.trade)
            paths.append(res.path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def _window(day, date, cfg):
    tz = day.index.tz
    lo = pd.Timestamp(f"{date} {cfg.first_signal}", tz=tz)
    hi = pd.Timestamp(f"{date} {cfg.last_signal}", tz=tz)
    return (day.index >= lo) & (day.index < hi), pd.Timestamp(f"{date} {cfg.time_exit}", tz=tz)


def _finish(date, day, i, d, entry, stop, target, cfg, t_exit, extra) -> DayResult:
    """Tamaño, simulación y registro de la operación que entra en la vela i."""
    dist = (entry - stop) * d
    qty = cfg.size(dist)
    if qty < 1:
        return DayResult(date, "riesgo_de_1_contrato_excede_limite")
    exit_price, exit_time, reason, path = _simulate(day.iloc[i:], d, entry, stop, target, qty, t_exit, cfg)
    comm = 2 * cfg.commission_side * qty
    gross = (exit_price - entry) * d * cfg.point_value * qty
    trade = {"date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": day.index[i],
             "entry": entry, "stop": stop, "target": target, "exit_time": exit_time, "exit": exit_price,
             "exit_reason": reason, "risk_usd": dist * cfg.point_value * qty,
             "gross": gross, "commission": comm, "pnl": gross - comm, **extra}
    return DayResult(date, "operada", trade, path)


def _run_mr_day(date, day, atr, cfg: MRConfig) -> DayResult:
    if atr is None or np.isnan(atr):
        return DayResult(date, "sin_atr")
    vwap = session_vwap(day)
    window, t_exit = _window(day, date, cfg)
    dev = (day.close - vwap).to_numpy()
    hits = np.flatnonzero(window & (np.abs(dev) > cfg.deviation_atr * atr))
    if len(hits) == 0:
        return DayResult(date, "sin_senal")
    s = hits[0]
    if s + 1 >= len(day):
        return DayResult(date, "sin_vela_de_entrada")
    d = -1 if dev[s] > 0 else 1                       # en contra de la desviación
    target = vwap.iloc[s]
    entry = day.open.iloc[s + 1] + d * cfg.slip_entry * cfg.tick
    reward = (target - entry) * d
    if reward <= 0:
        return DayResult(date, "precio_ya_en_el_vwap")
    stop = entry - d * cfg.stop_ratio * reward
    return _finish(date, day, s + 1, d, entry, stop, target, cfg, t_exit, {"desviacion": dev[s], "atr": atr})


def _run_vt_day(date, day, atr, cfg: VTConfig) -> DayResult:
    if atr is None or np.isnan(atr):
        return DayResult(date, "sin_atr")
    vwap = session_vwap(day)
    window, t_exit = _window(day, date, cfg)
    day_open = day.open.iloc[0]
    up = (day.close > vwap) & (day.close > day_open) & (day.low <= vwap)
    down = (day.close < vwap) & (day.close < day_open) & (day.high >= vwap)
    hits = np.flatnonzero(window & (up | down).to_numpy())
    if len(hits) == 0:
        return DayResult(date, "sin_senal")
    s = hits[0]
    if s + 1 >= len(day):
        return DayResult(date, "sin_vela_de_entrada")
    d = 1 if up.iloc[s] else -1
    entry = day.open.iloc[s + 1] + d * cfg.slip_entry * cfg.tick
    stop = vwap.iloc[s] - d * cfg.stop_atr * atr
    if (entry - stop) * d <= 0:
        return DayResult(date, "entrada_mas_alla_del_stop")
    target = entry + cfg.target_r * (entry - stop)   # vale para largos y cortos
    return _finish(date, day, s + 1, d, entry, stop, target, cfg, t_exit, {"atr": atr})
