"""Momentum de cierre en MNQ, con la misma estructura de backtest que la ORB de 5 minutos.

Reglas (config/close_momentum.yaml):
  1. Retorno de la mañana = cierre de la vela de 1 min de 9:59 - apertura de la de 9:30.
  2. Positivo -> largo; negativo -> corto; cero -> no se opera.
  3. Entrada en la apertura de la vela de 1 minuto de las 15:30 (con deslizamiento).
  4. Stop de emergencia al 10 % del ATR diario (14 días) desde el precio de entrada.
  5. Salida en la apertura de la vela de las 15:58. Una operación al día como máximo.

Se usan velas de 1 minuto porque 15:58 no coincide con el inicio de una vela de 5 minutos.
La simulación de la operación (stop, recorrido para Apex) es la misma función que en la ORB.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.strategies.orb_5m import DayResult, _simulate

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class CMConfig:
    point_value: float = 2.0
    tick: float = 0.25
    signal_start: str = "09:30"
    signal_end: str = "10:00"
    entry: str = "15:30"
    time_exit: str = "15:58"
    atr_days: int = 14
    stop_atr_pct: float = 0.10
    target_r: float | None = None
    risk_usd: float = 150.0
    max_contracts: int = 10
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 0
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path: str | Path = "config/close_momentum.yaml") -> "CMConfig":
        with open(ROOT / path, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        return cls(
            point_value=c["instrumento"]["valor_punto_usd"], tick=c["instrumento"]["tick"],
            signal_start=c["horario_et"]["inicio_senal"], signal_end=c["horario_et"]["fin_senal"],
            entry=c["horario_et"]["entrada"], time_exit=c["horario_et"]["salida_tiempo"],
            atr_days=c["atr_dias"], stop_atr_pct=c["stop"]["pct_atr"], target_r=c["take_profit_r"],
            risk_usd=c["riesgo"]["riesgo_por_operacion_usd"], max_contracts=c["riesgo"]["contratos_max"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "CMConfig":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        return f"CM_stop{self.stop_atr_pct:g}ATR_{self.risk_usd:g}$"


def backtest(minutes: pd.DataFrame, atr: pd.Series, cfg: CMConfig):
    """Misma salida que orb_5m.backtest: (trades, dias, recorridos)."""
    rth = minutes.between_time("09:30", "16:00", inclusive="left")
    trades, days, paths = [], [], []
    for date, day in rth.groupby(rth.index.date):
        res = _run_day(date, day, atr.get(date), cfg)
        days.append({"date": pd.Timestamp(date), "status": res.status})
        if res.trade:
            trades.append(res.trade)
            paths.append(res.path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def _run_day(date, day: pd.DataFrame, atr, cfg: CMConfig) -> DayResult:
    if atr is None or np.isnan(atr):
        return DayResult(date, "sin_atr")
    tz = day.index.tz
    ts = lambda hhmm: pd.Timestamp(f"{date} {hhmm}", tz=tz)  # noqa: E731
    t0, t_last = ts(cfg.signal_start), ts(cfg.signal_end) - pd.Timedelta(minutes=1)
    t_entry, t_exit = ts(cfg.entry), ts(cfg.time_exit)
    if t0 not in day.index or t_last not in day.index or t_entry not in day.index:
        return DayResult(date, "faltan_velas")
    move = day.at[t_last, "close"] - day.at[t0, "open"]
    if move == 0:
        return DayResult(date, "manana_plana")
    d = 1 if move > 0 else -1

    entry = day.at[t_entry, "open"] + d * cfg.slip_entry * cfg.tick
    stop = entry - d * cfg.stop_atr_pct * atr
    dist = cfg.stop_atr_pct * atr
    qty = int(np.floor(cfg.risk_usd / (dist * cfg.point_value) + 1e-9))
    if qty < 1:
        return DayResult(date, "riesgo_de_1_contrato_excede_limite")
    qty = min(qty, cfg.max_contracts)
    target = None if cfg.target_r is None else entry + d * cfg.target_r * dist

    trade_bars = day[day.index >= t_entry]
    exit_price, exit_time, reason, path = _simulate(trade_bars, d, entry, stop, target, qty, t_exit, cfg)
    comm = 2 * cfg.commission_side * qty
    gross = (exit_price - entry) * d * cfg.point_value * qty
    trade = {
        "date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": t_entry, "entry": entry,
        "stop": stop, "target": target, "exit_time": exit_time, "exit": exit_price, "exit_reason": reason,
        "morning_move": move, "atr": atr, "risk_usd": dist * cfg.point_value * qty,
        "gross": gross, "commission": comm, "pnl": gross - comm,
    }
    return DayResult(date, "operada", trade, path)
