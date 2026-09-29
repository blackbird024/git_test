"""Power of Three (PO3) / "Judas swing", traducido a reglas mecánicas comprobables.

La narrativa ("el precio está diseñado por el dinero inteligente") no se puede comprobar con un
backtest. Lo que sí se comprueba es esta regla concreta (config/po3_mnq.yaml, config/po3_mgc.yaml):

  1. Acumulación: máximo y mínimo del rango asiático (00:00-03:00 ET).
  2. Manipulación (03:00-05:00 ET): si el precio supera el máximo asiático pero NO el mínimo,
     barrida arriba -> sesgo BAJISTA (y al revés). Dos lados o ninguno -> no se opera.
  3. Distribución (08:00-11:00 ET), entrada a favor del sesgo:
       "sesgo":        en la apertura de la vela de las 8:00.
       "confirmacion": tras la primera vela de 5 min que cierra dentro del rango asiático y a favor
                       del sesgo (vela bajista si el sesgo es bajista); entrada en la vela siguiente.
  4. Stop detrás del extremo de la barrida (máximo/mínimo desde las 3:00 hasta la entrada) + 1 tick.
  5. Objetivo 2R o ninguno; salida por tiempo a las 15:45. Una operación al día.
"""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.strategies.orb_5m import DayResult, _simulate, to_bars

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class PO3Config:
    symbol: str = "MNQ"
    point_value: float = 2.0
    tick: float = 0.25
    bar_minutes: int = 5
    acc_start: str = "00:00"
    acc_end: str = "03:00"
    manip_end: str = "05:00"
    dist_start: str = "08:00"
    dist_end: str = "11:00"
    time_exit: str = "15:45"
    entry_mode: str = "sesgo"
    target_r: float | None = 2.0
    risk_usd: float = 250.0
    max_contracts: int = 10
    fixed_contracts: int | None = None
    commission_side: float = 1.0
    slip_entry: int = 1
    slip_stop: int = 1
    slip_time_exit: int = 0
    slip_target: int = 0

    @classmethod
    def from_yaml(cls, path) -> "PO3Config":
        c = yaml.safe_load(open(ROOT / path, encoding="utf-8"))
        h = c["horario_et"]
        return cls(
            symbol=c["instrumento"]["simbolo"], point_value=c["instrumento"]["valor_punto_usd"],
            tick=c["instrumento"]["tick"], bar_minutes=c["velas_minutos"],
            acc_start=h["acumulacion_inicio"], acc_end=h["acumulacion_fin"], manip_end=h["manipulacion_fin"],
            dist_start=h["distribucion_inicio"], dist_end=h["distribucion_fin"], time_exit=h["salida_tiempo"],
            entry_mode=c["entrada"], target_r=c["take_profit_r"],
            risk_usd=c["riesgo"]["riesgo_por_operacion_usd"], max_contracts=c["riesgo"]["contratos_max"],
            fixed_contracts=c["riesgo"]["contratos_fijos"],
            commission_side=c["costes"]["comision_por_contrato_y_lado_usd"],
            slip_entry=c["costes"]["slippage_ticks_entrada"], slip_stop=c["costes"]["slippage_ticks_stop"],
            slip_time_exit=c["costes"]["slippage_ticks_salida_tiempo"],
            slip_target=c["costes"]["slippage_ticks_take_profit"],
        )

    def variant(self, **changes) -> "PO3Config":
        return replace(self, **changes)

    @property
    def label(self) -> str:
        tgt = "tiempo" if self.target_r is None else f"{self.target_r:g}R"
        size = f"{self.fixed_contracts}contrato_fijo" if self.fixed_contracts else f"{self.risk_usd:g}$"
        return f"PO3_{self.symbol}_{self.entry_mode}_{tgt}_{size}"


def backtest(minutes: pd.DataFrame, atr, cfg: PO3Config):
    """(trades, días, recorridos), igual que el resto de estudios. `atr` no se usa."""
    bars = to_bars(minutes, cfg.bar_minutes, start=cfg.acc_start, end="16:00")
    trades, days, paths = [], [], []
    for date, day in bars.groupby(bars.index.date):
        res = _run_day(date, day, cfg)
        days.append({"date": pd.Timestamp(date), "status": res.status})
        if res.trade:
            trades.append(res.trade)
            paths.append(res.path)
    return pd.DataFrame(trades), pd.DataFrame(days), paths


def _run_day(date, day: pd.DataFrame, cfg: PO3Config) -> DayResult:
    tz = day.index.tz
    ts = lambda hhmm: pd.Timestamp(f"{date} {hhmm}", tz=tz)  # noqa: E731
    idx = day.index
    asia = day[(idx >= ts(cfg.acc_start)) & (idx < ts(cfg.acc_end))]
    manip = day[(idx >= ts(cfg.acc_end)) & (idx < ts(cfg.manip_end))]
    if len(asia) < 30 or len(manip) < 20:        # datos incompletos de la noche
        return DayResult(date, "noche_incompleta")
    ah, al = asia.high.max(), asia.low.min()
    swept_high, swept_low = manip.high.max() > ah, manip.low.min() < al
    if swept_high == swept_low:
        return DayResult(date, "barrida_ambos_lados" if swept_high else "sin_barrida")
    d = -1 if swept_high else 1                   # sesgo contrario a la barrida

    window = np.flatnonzero((idx >= ts(cfg.dist_start)) & (idx < ts(cfg.dist_end)))
    if len(window) == 0:
        return DayResult(date, "sin_velas_de_distribucion")
    if cfg.entry_mode == "sesgo":
        e = window[0]
    else:
        close, open_ = day.close.to_numpy(), day.open.to_numpy()
        inside = (close < ah) if d == -1 else (close > al)
        with_bias = (close < open_) if d == -1 else (close > open_)
        ok = [i for i in window if inside[i] and with_bias[i]]
        if not ok or ok[0] + 1 >= len(day) or idx[ok[0] + 1] >= ts(cfg.dist_end):
            return DayResult(date, "sin_confirmacion")
        e = ok[0] + 1

    since_manip = day[(idx >= ts(cfg.acc_end)) & (idx < idx[e])]
    stop = since_manip.high.max() + cfg.tick if d == -1 else since_manip.low.min() - cfg.tick
    entry = day.open.iloc[e] + d * cfg.slip_entry * cfg.tick
    dist = (entry - stop) * d
    if dist <= 0:
        return DayResult(date, "entrada_mas_alla_del_stop")
    if cfg.fixed_contracts:
        qty = cfg.fixed_contracts
    else:
        qty = int(np.floor(cfg.risk_usd / (dist * cfg.point_value) + 1e-9))
        if qty < 1:
            return DayResult(date, "riesgo_de_1_contrato_excede_limite")
        qty = min(qty, cfg.max_contracts)
    target = None if cfg.target_r is None else entry + d * cfg.target_r * dist

    exit_price, exit_time, reason, path = _simulate(day.iloc[e:], d, entry, stop, target, qty, ts(cfg.time_exit), cfg)
    comm = 2 * cfg.commission_side * qty
    gross = (exit_price - entry) * d * cfg.point_value * qty
    trade = {"date": pd.Timestamp(date), "direction": d, "qty": qty, "entry_time": idx[e], "entry": entry,
             "stop": stop, "target": target, "exit_time": exit_time, "exit": exit_price, "exit_reason": reason,
             "asia_high": ah, "asia_low": al, "risk_usd": dist * cfg.point_value * qty,
             "gross": gross, "commission": comm, "pnl": gross - comm}
    return DayResult(date, "operada", trade, path)
