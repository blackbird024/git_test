"""Motor cronológico vela a vela (una sesión tras otra; el capital se actualiza al cerrar cada operación).

REGLAS DE EJECUCIÓN (solo velas de 5 min: el orden dentro de la vela es desconocido; todas las hipótesis son conservadoras)
- Señal al CIERRE de la vela de retesteo → orden a mercado que se ejecuta en la APERTURA de la vela siguiente
  + slippage adverso (ticks configurables). Si esa vela empieza en o después de `entry_cutoff`, la señal se descarta.
- Stop (orden stop): si la vela abre más allá del stop → salida en la apertura (hueco) − slippage; si el mínimo
  (largos) toca el stop → salida en el stop − slippage.
- Objetivo (orden límite): si la vela abre más allá del objetivo → salida en la apertura (precio mejor; sin slippage);
  si no, solo se llena si el máximo supera el objetivo en `limit_fill_ticks_through` ticks → salida en el objetivo.
- En la vela de entrada también se comprueban stop y objetivo (la apertura es el primer precio de la vela).
- Stop y objetivo alcanzables en la misma vela → se supone el stop primero.
- Cierre obligatorio: a la apertura de la primera vela con inicio >= flat_time (15:55; en medias jornadas, 5 min antes
  del cierre anticipado), a mercado con slippage. Si no hay esa vela, al cierre de la última vela disponible − slippage.
- Una operación por sesión; sin promediar, sin ampliar el stop, sin break-even ni trailing.

SEÑAL (ver README): rango = velas que empiezan en [or_start, or_end); ruptura = primera vela cerrada después de
or_end con cierre estrictamente fuera; retesteo en las `retest_window_bars` velas siguientes: |mínimo − OR_high| <=
tolerancia (largos) y cierre > OR_high. Decisiones conservadoras no especificadas por el usuario:
  * un cierre de nuevo dentro del rango antes del retesteo invalida esa ruptura (`invalidate_on_close_inside`);
  * tras una ruptura descartada, otra ruptura en la misma sesión exige antes un cierre dentro del rango (no se
    persigue el precio);
  * sin filtro de estructura, se toma la primera ruptura de cualquier lado.
"""
import math
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd

from .bars import SessionBars
from .structure import Pivots, bias_at


@dataclass
class Trade:
    session: str
    instrument: str
    contract: Optional[str]
    bias: str
    or_high: float
    or_low: float
    side: str
    breakout_time: str
    retest_time: str
    retest_close: float
    retest_extreme: float
    signal_time: str
    entry_time: str
    entry_ideal: float
    entry: float
    stop: float
    target: float
    contracts: int
    equity_before: float
    risk_budget: float
    planned_risk_usd: float
    actual_risk_usd: float
    R_unit_usd: float
    exit_time: str = ""
    exit_ideal: float = float("nan")
    exit: float = float("nan")
    exit_reason: str = ""
    gross_usd: float = 0.0
    commission_usd: float = 0.0
    slippage_usd: float = 0.0
    net_usd: float = 0.0
    net_R: float = 0.0
    bars_held: int = 0
    warnings: str = ""


@dataclass
class SessionLog:
    session: str
    status: str                     # invalida | sin_senal | descartada_riesgo | descartada_hora | descartada_hueco | operada
    reason: str = ""
    bias: str = ""
    bias_detail: str = ""
    or_high: float = float("nan")
    or_low: float = float("nan")


def _tick_round(x, tick):
    return round(round(x / tick) * tick, 10)


def run(sessions, pivots: Pivots, cfg, use_filter: Optional[bool] = None, costs=None, risk=None):
    st = cfg.strategy
    inst = cfg.instrument
    costs = costs or cfg.costs
    risk = risk or cfg.risk
    use_filter = st.use_structure_filter if use_filter is None else use_filter
    tick = inst.tick_size
    slip = costs.slippage_ticks_per_side * tick
    fee_side = costs.commission_per_side + costs.extra_cost_per_side
    equity = risk.initial_capital
    trades, logs = [], []
    for s in sessions:
        key = str(s.date.date())
        if s.invalid_reason:
            logs.append(SessionLog(key, "invalida", s.invalid_reason)); continue
        starts = s.start
        times = np.array([x.time() for x in starts])
        # ── rango
        in_or = (times >= st.or_start) & (times < st.or_end)
        expected = int((st.or_end.hour * 60 + st.or_end.minute - st.or_start.hour * 60 - st.or_start.minute) / cfg.bar_minutes)
        if in_or.sum() != expected:
            logs.append(SessionLog(key, "invalida", f"rango incompleto ({int(in_or.sum())}/{expected} velas)")); continue
        orh, orl = float(s.h[in_or].max()), float(s.l[in_or].min())
        if not orh > orl:
            logs.append(SessionLog(key, "invalida", "rango de tamaño cero")); continue
        # ── sesgo (información disponible a la apertura de la sesión)
        t_open = pd.Timestamp.combine(s.date.date(), st.session_start).tz_localize(cfg.timezone)
        bias, det = bias_at(pivots, t_open)
        if use_filter:
            allowed = {"alcista": (1,), "bajista": (-1,)}.get(bias, ())
        else:
            allowed = (1, -1)
        log = SessionLog(key, "sin_senal", "", bias, str(det), orh, orl)
        if not allowed:
            log.reason = "sesgo neutral"
            logs.append(log); continue
        # ── máquina de estados sobre velas cerradas posteriores al rango
        after = np.nonzero(times >= st.or_end)[0]
        state, side, brk_i, count, armed = "wait", 0, -1, 0, True
        signal_i = None
        for i in after:
            c, h, l = s.c[i], s.h[i], s.l[i]
            inside = orl <= c <= orh
            if state == "wait":
                if not armed:
                    armed = inside
                    continue
                d = 1 if c > orh else (-1 if c < orl else 0)
                if d and d in allowed:
                    state, side, brk_i, count = "retest", d, i, 0
                continue
            count += 1
            lvl = orh if side == 1 else orl
            if (side == 1 and c < orl) or (side == -1 and c > orh):
                state, armed = "wait", False                      # cierre al otro lado: ruptura descartada
                d = -side
                if d in allowed:
                    state, side, brk_i, count, armed = "retest", d, i, 0, True
                continue
            if inside and st.invalidate_on_close_inside:
                state, armed = "wait", True                       # volvió dentro: ruptura invalidada (ya re-armada)
                continue
            ext = l if side == 1 else h
            touched = abs(ext - lvl) <= st.retest_tolerance_ticks * tick + 1e-9
            beyond = c > orh if side == 1 else c < orl
            if touched and beyond:
                signal_i = i
                break
            if count >= st.retest_window_bars:
                state, armed = "wait", False
        if signal_i is None:
            log.reason = "sin ruptura con retesteo válido"
            logs.append(log); continue
        i = signal_i
        k = i + 1
        if k >= len(times) or times[k] >= st.entry_cutoff or times[k] >= s.flat_time:
            log.status, log.reason = "descartada_hora", "la vela de entrada empieza en/tras la hora límite"
            logs.append(log); continue
        retest_ext = s.l[i] if side == 1 else s.h[i]
        stop = _tick_round(retest_ext - side * st.stop_offset_ticks * tick, tick)
        # ── tamaño con el precio estimado (cierre del retesteo + slippage); se mantiene al ejecutar
        est_entry = s.c[i] + side * slip
        est_risk_pts = side * (est_entry - stop)
        if est_risk_pts <= 0:
            log.status, log.reason = "descartada_riesgo", "riesgo estimado <= 0"
            logs.append(log); continue
        loss_pc = est_risk_pts * inst.point_value + 2 * fee_side + slip * inst.point_value
        base_cap = equity if risk.compounding else risk.initial_capital
        budget = base_cap * risk.risk_pct
        if risk.sizing_mode == "fixed":
            n = risk.fixed_contracts
        else:
            n = int(math.floor(budget / loss_pc + 1e-12))
            if risk.max_contracts:
                n = min(n, risk.max_contracts)
        if n <= 0:
            log.status, log.reason = "descartada_riesgo", f"1 contrato arriesga {loss_pc:.2f} > presupuesto {budget:.2f}"
            logs.append(log); continue
        entry_ideal = s.o[k]
        entry = entry_ideal + side * slip
        if side * (entry - stop) <= 0:
            log.status, log.reason = "descartada_hueco", "la apertura de entrada ya está más allá del stop"
            logs.append(log); continue
        risk_pts = side * (entry - stop)
        target = _tick_round(entry + side * st.reward_risk * risk_pts, tick)
        r_unit = n * risk_pts * inst.point_value
        actual_risk = n * (risk_pts * inst.point_value + 2 * fee_side + slip * inst.point_value)
        tr = Trade(key, inst.symbol, s.contract, bias, orh, orl, "largo" if side == 1 else "corto",
                   str(starts[brk_i]), str(starts[i]), float(s.c[i]), float(retest_ext),
                   str(starts[i] + pd.Timedelta(minutes=cfg.bar_minutes)), str(starts[k]), float(entry_ideal),
                   float(entry), float(stop), float(target), n, equity, budget, n * loss_pc, actual_risk, r_unit)
        if risk.sizing_mode == "percent" and actual_risk > budget + 1e-9:
            tr.warnings = f"riesgo real {actual_risk:.2f} > presupuesto {budget:.2f} (la apertura se alejó del cierre del retesteo)"
        # ── gestión
        thr = costs.limit_fill_ticks_through * tick
        xi, xideal, xfill, why = None, None, None, None
        for j in range(k, len(times)):
            if times[j] >= s.flat_time:
                xi, xideal, xfill, why = j, s.o[j], s.o[j] - side * slip, "cierre_obligatorio"
                break
            o, h, l = s.o[j], s.h[j], s.l[j]
            first = j == k
            if side == 1:
                if not first and o <= stop:
                    xi, xideal, xfill, why = j, o, o - slip, "stop_hueco"; break
                if l <= stop:
                    xi, xideal, xfill, why = j, stop, stop - slip, "stop"; break
                if not first and o >= target:
                    xi, xideal, xfill, why = j, o, o, "objetivo_hueco"; break
                if h >= target + thr:
                    xi, xideal, xfill, why = j, target, target, "objetivo"; break
            else:
                if not first and o >= stop:
                    xi, xideal, xfill, why = j, o, o + slip, "stop_hueco"; break
                if h >= stop:
                    xi, xideal, xfill, why = j, stop, stop + slip, "stop"; break
                if not first and o <= target:
                    xi, xideal, xfill, why = j, o, o, "objetivo_hueco"; break
                if l <= target - thr:
                    xi, xideal, xfill, why = j, target, target, "objetivo"; break
        if xi is None:
            xi = len(times) - 1
            xideal, xfill, why = s.c[xi], s.c[xi] - side * slip, "fin_de_datos"
            tr.warnings += " | sin vela de cierre obligatorio: salida al último cierre"
        tr.exit_time = str(starts[xi] + pd.Timedelta(minutes=cfg.bar_minutes)) if why == "fin_de_datos" else str(starts[xi])
        tr.exit_ideal, tr.exit, tr.exit_reason = float(xideal), float(xfill), why
        tr.gross_usd = side * (xideal - entry_ideal) * inst.point_value * n
        tr.slippage_usd = (abs(entry - entry_ideal) + abs(xfill - xideal)) * inst.point_value * n
        tr.commission_usd = 2 * fee_side * n
        tr.net_usd = tr.gross_usd - tr.slippage_usd - tr.commission_usd
        tr.net_R = tr.net_usd / r_unit
        tr.bars_held = xi - k + 1
        equity += tr.net_usd
        trades.append(tr)
        log.status, log.reason = "operada", why
        logs.append(log)
    return trades, logs, equity


def trades_df(trades):
    return pd.DataFrame([asdict(t) for t in trades])


def logs_df(logs):
    return pd.DataFrame([asdict(x) for x in logs])
