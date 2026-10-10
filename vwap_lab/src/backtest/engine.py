"""Motor de backtesting vela a vela (5 min) y gestión de capital.

Ejecución (solo velas de 5 min; orden dentro de la vela desconocido → supuestos conservadores):
- Señal al cierre de la vela t → entrada a mercado en la APERTURA de t+1 + slippage. La vela t+1 debe empezar antes de
  `entry_end`; si no, no hay entrada.
- Stop: mínimo (largos) de la vela de referencia − buffer; o, en la prueba separada, entrada ∓ k·ATR.
  Si la vela abre más allá del stop → salida en la apertura (hueco) − slippage; si lo toca → en el stop − slippage.
- Objetivo k·R (límite): si la vela abre más allá → en la apertura; si no, solo si lo supera en 1 tick.
- Stop y objetivo alcanzables en la misma vela → stop primero; la operación se marca como "ambigua".
- Cierre obligatorio en la apertura de la vela de `flat` (11:00 Londres / 15:55 Nueva York) − slippage.
- Máximo `max_trades` por sesión, una posición a la vez; la siguiente señal tiene que producirse después de la salida.
- Descartes: riesgo por contrato < min_risk_to_cost × coste ida y vuelta ("stop demasiado pequeño"); contratos = 0
  ("un contrato supera el riesgo"); entrada ya al otro lado del stop ("hueco").
- Límite diario opcional: tras perder `daily_loss_stop_R` R realizados en la sesión, no se abren más operaciones.
Tamaño: floor(capital × riesgo% / (riesgo_puntos × valor_punto + comisión ida y vuelta + slippage de salida)).
"""
import math
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class Trade:
    instrument: str
    session: str
    date: str
    strategy: str
    threshold: object
    target_R: float
    side: int
    signal_time: str
    entry_time: str
    exit_time: str
    entry: float
    stop: float
    target: float
    exit: float
    exit_reason: str
    contracts: int
    risk_pts: float
    planned_risk_usd: float
    gross_usd: float
    commission_usd: float
    slippage_usd: float
    net_usd: float
    R: float
    ambiguous: bool
    slope: float
    hour: int
    equity_before: float


def run_session(sess, arr, sig_side, sig_ref, inst, costs, p, risk, equity, strat, thr, target_R, stop_mode="bar",
                max_trades=2, daily_loss_R=None, skipped=None, bar_minutes=5):
    tick, pv = inst["tick_size"], inst["point_value"]
    slip = costs["slippage_ticks_per_side"] * tick
    comm = costs["commission_per_side"]
    thr_ticks = costs.get("limit_fill_ticks_through", 1) * tick
    o, h, l, c = arr["o"], arr["h"], arr["l"], arr["c"]
    start = sess.start
    n = len(c)
    fp = sess.flat_pos if sess.flat_pos >= 0 else n
    ee = sess.entry_end.hour * 60 + sess.entry_end.minute
    trades = []
    free = -1
    realized_R = 0.0
    t = 0
    while t < n - 1 and len(trades) < max_trades:
        if t <= free or sig_side[t] == 0 or t + 1 >= fp:
            t += 1
            continue
        if daily_loss_R is not None and realized_R <= -daily_loss_R:
            break
        k = t + 1
        if start[k].hour * 60 + start[k].minute >= ee:
            break
        s = sig_side[t]
        r = sig_ref[t]
        buf = p["stop_buffer_ticks"] * tick
        if stop_mode == "bar":
            stop = l[r] - buf if s == 1 else h[r] + buf
        else:
            stop = round((o[k] - s * p["atr_stop_mult"] * arr["atr"][t]) / tick) * tick
        entry_ideal = o[k]
        entry = entry_ideal + s * slip
        risk_pts = s * (entry - stop)
        if risk_pts <= 0:
            if skipped is not None: skipped["hueco"] += 1
            t += 1; continue
        rt_cost = 2 * comm + 2 * slip * pv
        if risk_pts * pv < p["min_risk_to_cost"] * rt_cost:
            if skipped is not None: skipped["stop_pequeno"] += 1
            t += 1; continue
        budget = (equity if risk["compounding"] else risk["initial_capital"]) * risk["risk_pct"]
        loss_pc = risk_pts * pv + 2 * comm + slip * pv
        nc = int(math.floor(budget / loss_pc + 1e-12))
        if nc <= 0:
            if skipped is not None: skipped["riesgo"] += 1
            t += 1; continue
        target = round((entry + s * target_R * risk_pts) / tick) * tick
        xi, xid, xf, why, amb = None, None, None, None, False
        for j in range(k, n):
            if j >= fp:
                xi, xid, xf, why = j, o[j], o[j] - s * slip, "cierre_sesion"; break
            first = j == k
            hit_stop = (l[j] <= stop) if s == 1 else (h[j] >= stop)
            hit_tgt = (h[j] >= target + thr_ticks) if s == 1 else (l[j] <= target - thr_ticks)
            if not first and ((o[j] <= stop) if s == 1 else (o[j] >= stop)):
                xi, xid, xf, why = j, o[j], o[j] - s * slip, "stop_hueco"; break
            if hit_stop:
                amb = bool(hit_tgt)
                xi, xid, xf, why = j, stop, stop - s * slip, "stop"; break
            if not first and ((o[j] >= target) if s == 1 else (o[j] <= target)):
                xi, xid, xf, why = j, o[j], o[j], "objetivo_hueco"; break
            if hit_tgt:
                xi, xid, xf, why = j, target, target, "objetivo"; break
        if xi is None:
            xi = n - 1
            xid, xf, why = c[xi], c[xi] - s * slip, "fin_datos"
        gross = s * (xid - entry_ideal) * pv * nc
        slip_usd = (abs(entry - entry_ideal) + abs(xf - xid)) * pv * nc
        comm_usd = 2 * comm * nc
        net = gross - slip_usd - comm_usd
        R = net / (risk_pts * pv * nc)
        trades.append(Trade(inst["symbol"], sess.name, str(sess.date.date()), strat, thr, target_R, s,
                            str(start[t] + pd.Timedelta(minutes=bar_minutes)), str(start[k]), str(start[xi]), entry, stop, target,
                            xf, why, nc, risk_pts, nc * loss_pc, gross, comm_usd, slip_usd, net, R, amb,
                            float(arr["slope"][t]), int(start[t].hour), equity))
        equity += net
        realized_R += R
        free = xi - 1                 # una señal al cierre de la vela de salida ya es posterior a la salida
        t = xi
    return trades, equity


def to_df(trades):
    return pd.DataFrame([asdict(t) for t in trades])
