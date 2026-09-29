"""Motor de backtest vela a vela (velas de 1 minuto, hora de Nueva York).

Cómo funciona, minuto a minuto y para cada instrumento:
  1. Entradas pendientes: si una señal se conoció en una vela anterior, se entra en la APERTURA
     de esta vela, pagando deslizamiento. Antes, el gestor de riesgo decide si se permite y con
     cuántos contratos.
  2. Cierre forzado: a partir de la hora límite se cierra todo al precio de apertura.
  3. Stops y objetivos: se comprueba si el máximo o el mínimo de la vela los tocaron.
     Si en la MISMA vela se tocan los dos, asumimos que saltó el stop, porque con velas de
     1 minuto no sabemos cuál ocurrió primero (supuesto pesimista a propósito).
  4. Peor momento del día: calculamos cuánto se iba perdiendo contando lo no realizado al PEOR
     precio de la vela. Es el dato que necesita la regla de drawdown de Apex.
  5. Señales nuevas: las que se conocen al cierre de esta vela se programan para la siguiente.

El motor no sabe nada de Apex. Solo produce operaciones y un resumen diario.
Las reglas de la cuenta se aplican después, en src/risk/apex_eod.py.
"""
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from src.config import Instrument, SystemRules
from src.engine.types import Position, Signal, Trade
from src.risk.sizing import contracts_for_risk, loss_per_contract

SESSION_END = "16:00"


class Strategy(Protocol):
    name: str

    def signals_for_day(self, date, bars: dict[str, pd.DataFrame]) -> list[Signal]:
        """Devuelve las señales del día. Cada señal solo puede usar velas hasta `signal.time`."""
        ...


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    daily: pd.DataFrame         # columnas: pnl, min_intraday_pnl, n_trades
    rejected: pd.DataFrame      # señales descartadas y el motivo (para auditar)


@dataclass
class _DayState:
    realized: float = 0.0
    min_equity: float = 0.0
    n_entries: int = 0
    open_positions: list[Position] = field(default_factory=list)
    pending: list[tuple[pd.Timestamp, Signal]] = field(default_factory=list)


class Backtester:
    def __init__(self, instruments: dict[str, Instrument], rules: SystemRules, max_micros: int):
        self.instruments = instruments
        self.rules = rules
        self.max_micros = max_micros

    # ------------------------------------------------------------------ API
    def run(self, data: dict[str, pd.DataFrame], strategies: list[Strategy]) -> BacktestResult:
        sessions = {sym: df.between_time(self.rules.session_start, SESSION_END, inclusive="left")
                    for sym, df in data.items()}
        all_dates = sorted(set().union(*[set(df.index.date) for df in sessions.values()]))
        by_day = {sym: dict(tuple(df.groupby(df.index.date))) for sym, df in sessions.items()}

        trades, daily, rejected = [], [], []
        for date in all_dates:
            bars = {sym: d[date] for sym, d in by_day.items() if date in d}
            signals = [s for strat in strategies for s in strat.signals_for_day(date, bars)]
            day_trades, summary, day_rejected = self._run_day(date, bars, signals)
            trades += day_trades
            rejected += day_rejected
            daily.append(summary)

        trades_df = pd.DataFrame([t.__dict__ for t in trades])
        daily_df = pd.DataFrame(daily).set_index("date") if daily else pd.DataFrame()
        return BacktestResult(trades_df, daily_df, pd.DataFrame(rejected))

    # ------------------------------------------------------------ un día
    def _run_day(self, date, bars: dict[str, pd.DataFrame], signals: list[Signal]):
        st = _DayState()
        trades: list[Trade] = []
        rejected: list[dict] = []
        force_close = pd.Timestamp(f"{date} {self.rules.force_close}").time()

        # Programar cada señal para la apertura de la vela correspondiente (retraso humano).
        for sig in signals:
            df = bars.get(sig.instrument)
            if df is None:
                continue
            later = df.index[df.index > sig.time]
            idx = self.rules.entry_delay_bars - 1
            if len(later) > idx:
                st.pending.append((later[idx], sig))
            else:
                rejected.append(self._reject(sig, "sin_vela_para_entrar"))

        # Diccionarios {hora: vela} para leer cada vela rápido (itertuples es mucho más veloz que .loc).
        rows = {sym: {r.Index: r for r in df.itertuples()} for sym, df in bars.items()}
        timeline = sorted(set().union(*[set(r) for r in rows.values()]))
        last_close = {}
        for ts in timeline:
            for sym, sym_rows in rows.items():
                bar = sym_rows.get(ts)
                if bar is None:
                    continue
                inst = self.instruments[sym]

                last_close[sym] = bar
                if ts.time() >= force_close:
                    for pos in [p for p in st.open_positions if p.signal.instrument == sym]:
                        exit_px = bar.open - pos.signal.direction * inst.slippage
                        trades.append(self._close(st, pos, ts, exit_px, "cierre_forzado"))
                    for t, sig in [(t, s) for t, s in st.pending if s.instrument == sym]:
                        st.pending.remove((t, sig))
                        rejected.append(self._reject(sig, "despues_de_hora_limite"))
                else:
                    due = [(t, s) for t, s in st.pending if t == ts and s.instrument == sym] if st.pending else []
                    for t, sig in due:
                        st.pending.remove((t, sig))
                        reason = self._try_enter(st, sig, ts, bar, inst)
                        if reason:
                            rejected.append(self._reject(sig, reason))
                    # Peor momento ANTES de las salidas: la vela pudo bajar mucho antes de tocar el objetivo.
                    self._update_min_equity(st, last_close)
                    for pos in [p for p in st.open_positions if p.signal.instrument == sym]:
                        trade = self._check_exit(st, pos, ts, bar, inst)
                        if trade:
                            trades.append(trade)
                self._update_min_equity(st, last_close)

        # Red de seguridad: si faltan velas al final del día, cerrar al último precio conocido.
        for pos in list(st.open_positions):
            bar = last_close[pos.signal.instrument]
            inst = self.instruments[pos.signal.instrument]
            exit_px = bar.close - pos.signal.direction * inst.slippage
            trades.append(self._close(st, pos, bar.Index, exit_px, "cierre_forzado"))
            st.min_equity = min(st.min_equity, st.realized)

        summary = {"date": pd.Timestamp(date), "pnl": st.realized,
                   "min_intraday_pnl": st.min_equity, "n_trades": len(trades)}
        return trades, summary, rejected

    # ------------------------------------------------------ gestor de riesgo
    def _try_enter(self, st: _DayState, sig: Signal, ts, bar, inst: Instrument) -> str | None:
        """Intenta abrir la posición. Devuelve el motivo del rechazo, o None si entró."""
        if st.n_entries >= self.rules.max_trades_per_day:
            return "max_operaciones_dia"
        for p in st.open_positions:
            if (self.instruments[p.signal.instrument].group == inst.group
                    and p.signal.direction != sig.direction):
                return "posicion_opuesta_correlacionada"

        entry = bar.open + sig.direction * inst.slippage
        # El stop y el objetivo tienen que seguir al otro lado del precio de entrada.
        if (entry - sig.stop) * sig.direction <= 0 or (sig.target - entry) * sig.direction <= 0:
            return "precio_ya_paso_stop_u_objetivo"
        reward = abs(sig.target - entry)
        if reward < self.rules.min_reward_risk * abs(entry - sig.stop):
            return "ratio_objetivo_stop_insuficiente"

        open_risk = sum(p.risk_usd for p in st.open_positions)
        budget_left = self.rules.daily_budget + st.realized - open_risk
        risk_allowed = min(self.rules.risk_per_trade, budget_left)
        qty = contracts_for_risk(inst, entry, sig.stop, risk_allowed)
        qty = min(qty, self.max_micros - sum(p.qty for p in st.open_positions))
        if qty <= 0:
            return "sin_presupuesto_de_riesgo"

        st.open_positions.append(Position(sig, qty, ts, entry,
                                          qty * loss_per_contract(inst, entry, sig.stop)))
        st.n_entries += 1
        return None

    # ------------------------------------------------------------ salidas
    def _check_exit(self, st: _DayState, pos: Position, ts, bar, inst: Instrument) -> Trade | None:
        d = pos.signal.direction
        stop, target = pos.signal.stop, pos.signal.target
        hit_stop = bar.low <= stop if d > 0 else bar.high >= stop
        hit_target = bar.high >= target if d > 0 else bar.low <= target
        if hit_stop:  # si se tocan los dos en la misma vela, gana el stop (pesimista)
            # Si el precio abre ya más allá del stop (hueco), se ejecuta en la apertura.
            base = min(stop, bar.open) if d > 0 else max(stop, bar.open)
            return self._close(st, pos, ts, base - d * inst.slippage, "stop")
        if hit_target:
            return self._close(st, pos, ts, target, "target")  # orden límite: sin deslizamiento
        return None

    def _close(self, st: _DayState, pos: Position, ts, exit_px: float, reason: str) -> Trade:
        inst = self.instruments[pos.signal.instrument]
        gross = (exit_px - pos.entry_price) * pos.signal.direction * inst.point_value * pos.qty
        costs = inst.commission_rt * pos.qty
        st.open_positions.remove(pos)
        st.realized += gross - costs
        s = pos.signal
        return Trade(s.strategy, s.instrument, s.direction, pos.qty, pos.entry_time, pos.entry_price,
                     ts, exit_px, reason, gross, costs, gross - costs, pos.risk_usd)

    def _update_min_equity(self, st: _DayState, last_bar: dict) -> None:
        st.min_equity = min(st.min_equity, st.realized + self._worst_unrealized(st, last_bar))

    def _worst_unrealized(self, st: _DayState, last_bar: dict) -> float:
        """P&L no realizado al peor precio de la vela actual (mínimo si largo, máximo si corto)."""
        total = 0.0
        for p in st.open_positions:
            inst = self.instruments[p.signal.instrument]
            bar = last_bar[p.signal.instrument]
            # El stop limita lo peor que se puede ver (salvo hueco en la apertura).
            if p.signal.direction > 0:
                worst = max(bar.low, min(p.signal.stop, bar.open) - inst.slippage)
            else:
                worst = min(bar.high, max(p.signal.stop, bar.open) + inst.slippage)
            total += ((worst - p.entry_price) * p.signal.direction * inst.point_value * p.qty
                      - inst.commission_rt * p.qty)
        return total

    @staticmethod
    def _reject(sig: Signal, reason: str) -> dict:
        return {"strategy": sig.strategy, "instrument": sig.instrument, "time": sig.time,
                "direction": sig.direction, "reason": reason}
