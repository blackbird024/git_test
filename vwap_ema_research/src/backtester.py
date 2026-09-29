"""Motor de backtest cronológico: decisión al cierre de velas de 15 min, ejecución en la apertura de la siguiente,
stops/targets resueltos con los minutos de la vela. Una posición por instrumento, sin pyramiding, sin overnight.

Salidas (p["exit_type"]):
  vwap              cierre por el otro lado del VWAP -> salida en la apertura siguiente (+ stop inicial)
  ema20             cierre por el otro lado de la EMA20 -> salida en la apertura siguiente (+ stop inicial)
  atr_trailing      stop que sigue al mejor cierre a trailing_atr_multiplier x ATR (se actualiza al cierre)
  fixed             stop + objetivo fijos (objetivo = take_profit_R, o 2R si no se indica)
  partial_trailing  en partial_at_R se cierra partial_fraction (si hay >= 2 contratos), el stop pasa a la entrada y
                    luego sigue con trailing ATR
  time              salida en la apertura tras time_exit_minutes desde la entrada (+ stop inicial)
Todas: take_profit_R opcional (salvo trailing/parcial), cierre forzado a eod_exit.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_loader import hhmm
from .execution import Costs, check_subbar
from .risk import Risk
from .strategy import entry_signals, exit_signals


@dataclass
class Result:
    trades: pd.DataFrame
    daily: pd.DataFrame
    counters: dict
    capital: float


def costs_for(inst: dict, slippage_mult: float = 1.0) -> Costs:
    return Costs(inst["tick_size"], inst["point_value"], inst["commission_per_side"],
                 inst["slippage_ticks"] * slippage_mult, inst["spread_ticks"])


def select(x: pd.DataFrame, desde=None, hasta=None) -> np.ndarray:
    ses = pd.to_datetime(x.session.astype(str))
    m = x.session_valid.to_numpy(bool).copy()
    if desde is not None:
        m &= (ses >= pd.Timestamp(desde)).to_numpy()
    if hasta is not None:
        m &= (ses <= pd.Timestamp(hasta)).to_numpy()
    return m


def run(x: pd.DataFrame, sub: dict, p: dict, inst: dict, capital: float, desde=None, hasta=None,
        slippage_mult: float = 1.0, sig_override=None) -> Result:
    cm = costs_for(inst, slippage_mult)
    pv, tick = inst["point_value"], inst["tick_size"]
    rk = Risk(inst.get("sizing_override", p["sizing"]), p["risk_per_trade"], p["fixed_contracts"], p["max_contracts"],
              pv, p["daily_loss_limit"], p["max_consecutive_losses"], p["max_trades_per_day"])
    sig = entry_signals(x, p) if sig_override is None else sig_override
    exL, exS = exit_signals(x, p["exit_type"])
    et = p["exit_type"]
    tp_r = p["take_profit_R"] if et not in ("atr_trailing", "partial_trailing") else None
    if et == "fixed" and tp_r is None:
        tp_r = 2.0
    trail = p["trailing_atr_multiplier"] if et in ("atr_trailing", "partial_trailing") else None
    win = (hhmm(p["window"][0]), hhmm(p["window"][1])) if p.get("window") else None
    last_entry, eod, paso = hhmm(inst["last_entry"]), hhmm(inst["eod_exit"]), 15
    O, C, A = x.open.to_numpy(), x.close.to_numpy(), x.atr.to_numpy()
    SL, SH = x.struct_low.to_numpy(), x.struct_high.to_numpy()
    MN, I0, I1 = x.start_min.to_numpy(), x.i0.to_numpy(), x.i1.to_numpy()
    T = x.start.dt.tz_localize(None).to_numpy()
    so, sh, sl_, stime = sub["open"], sub["high"], sub["low"], sub["time"]
    ses = x.session.to_numpy()
    sel = np.flatnonzero(select(x, desde, hasta))
    equity = capital
    trades, daily, cnt = [], [], Counter()
    if len(sel) == 0:
        return Result(pd.DataFrame(), pd.DataFrame(columns=["session", "pnl", "gross", "equity"]), {}, capital)
    ss = ses[sel]
    for idxs in np.split(sel, np.flatnonzero(ss[1:] != ss[:-1]) + 1):
        rk.new_day(equity)
        pos, pend_exit, pend_entry = None, None, None
        pnl_d = gross_d = 0.0

        def realizar(q, bruto_px, fill_px):
            nonlocal equity, pnl_d, gross_d
            d = pos["d"]
            g = (bruto_px - pos["raw"]) * d * q * pv
            n = (fill_px - pos["fill"]) * d * q * pv - cm.commission(q)
            pos["gross"] += g
            pos["net"] += n
            pos["open_qty"] -= q
            equity += n
            pnl_d += n
            gross_d += g

        def cerrar(bruto_px, fill_px, t, motivo, k):
            nonlocal pos
            realizar(pos["open_qty"], bruto_px, fill_px)
            rk.closed(pos["net"])
            riesgo = pos["qty"] * pos["dist"] * pv
            trades.append({"session": ses[k], "direction": pos["d"], "qty": pos["qty"], "entry_time": pos["t"],
                           "entry_price": pos["fill"], "raw_entry": pos["raw"], "exit_time": t, "exit_price": fill_px,
                           "stop_initial": pos["stop0"], "take_profit": pos["target0"], "exit_reason": motivo,
                           "partial": pos["partial_done"], "gross_pnl": pos["gross"], "costs": pos["gross"] - pos["net"],
                           "net_pnl": pos["net"], "risk_usd": riesgo, "r_net": pos["net"] / riesgo,
                           "r_gross": pos["gross"] / riesgo, "mae_pts": pos["mae"], "mfe_pts": pos["mfe"],
                           "minutes": (pd.Timestamp(t) - pd.Timestamp(pos["t"])).total_seconds() / 60,
                           "entry_min": pos["mn"], "atr_entry": pos["atr"], "stop_pts": pos["dist"]})
            pos = None

        def abrir(d, k, info):
            nonlocal pos
            porque = rk.can_open()
            if porque:
                cnt[porque] += 1
                return
            atr_k, sl_k, sh_k = info
            fill = cm.market(O[k], d, entry=True)
            if p["stop_type"] == "atr":
                if not (np.isfinite(atr_k) and atr_k > 0):
                    cnt["sin_atr"] += 1
                    return
                dist = p["atr_multiplier"] * atr_k
            else:                                           # estructura: mín/máx de las últimas N velas -1 tick
                nivel = sl_k - tick if d == 1 else sh_k + tick
                dist = (fill - nivel) * d
                if not dist > 0:
                    cnt["stop_estructura_invalido"] += 1
                    return
            q = rk.size(equity, dist)
            if q < 1:
                cnt["tamano_menor_que_1"] += 1
                return
            stop = fill - d * dist
            target = fill + d * tp_r * dist if tp_r is not None else None
            pos = {"d": d, "qty": q, "open_qty": q, "fill": fill, "raw": O[k], "t": T[k], "dist": dist, "stop": stop,
                   "stop0": stop, "target": target, "target0": target, "mae": 0.0, "mfe": 0.0, "bars": 0, "best": fill,
                   "mn": MN[k], "atr": atr_k, "gross": 0.0, "net": 0.0, "partial_done": False,
                   "partial_px": fill + d * p["partial_at_R"] * dist if et == "partial_trailing" else None,
                   "trail_on": et == "atr_trailing"}
            rk.opened()
            cnt["entradas"] += 1

        for n_k, k in enumerate(idxs):
            if pend_exit is not None and pos is not None:
                cerrar(O[k], cm.market(O[k], pos["d"], entry=False), T[k], pend_exit, k)
            pend_exit = None
            if pend_entry is not None and pos is None:
                abrir(pend_entry[0], k, pend_entry[2])          # se ejecuta en la apertura de ESTA vela (k)
            pend_entry = None
            if MN[k] >= eod:
                if pos is not None:
                    cerrar(O[k], cm.market(O[k], pos["d"], entry=False), T[k], "fin_de_sesion", k)
                continue
            if pos is not None:
                d = pos["d"]
                for j in range(I0[k], I1[k] + 1):
                    pos["mfe"] = max(pos["mfe"], (sh[j] - pos["fill"]) if d == 1 else (pos["fill"] - sl_[j]))
                    pos["mae"] = max(pos["mae"], (pos["fill"] - sl_[j]) if d == 1 else (sh[j] - pos["fill"]))
                    r = check_subbar(so[j], sh[j], sl_[j], d, pos["stop"], pos["target"], tick)
                    if r is not None:
                        motivo = r[0] if not (r[0] == "stop" and pos["stop"] != pos["stop0"]) else "trailing_o_breakeven"
                        fill = cm.market(r[1], d, entry=False) if r[0] == "stop" else r[1]
                        cerrar(r[1], fill, stime[j], motivo, k)
                        break
                    if pos["partial_px"] is not None and not pos["partial_done"] and \
                            ((sh[j] >= pos["partial_px"] + tick) if d == 1 else (sl_[j] <= pos["partial_px"] - tick)):
                        px = max(so[j], pos["partial_px"]) if d == 1 else min(so[j], pos["partial_px"])
                        q_p = int(np.floor(pos["qty"] * p["partial_fraction"]))
                        if q_p >= 1:
                            realizar(q_p, px, px)
                        pos["partial_done"], pos["trail_on"] = True, True
                        pos["stop"] = pos["fill"]                    # resto a precio de entrada (breakeven)
            hay_sig = n_k + 1 < len(idxs)
            if pos is not None:
                pos["bars"] += 1
                if pos["trail_on"] and trail is not None and np.isfinite(A[k]):
                    pos["best"] = max(pos["best"], C[k]) if pos["d"] == 1 else min(pos["best"], C[k])
                    cand = pos["best"] - pos["d"] * trail * A[k]
                    if (cand - pos["stop"]) * pos["d"] > 0:
                        pos["stop"] = cand
                if hay_sig:
                    if (exL[k] if pos["d"] == 1 else exS[k]):
                        pend_exit = f"senal_{et}"
                    elif et == "time" and pos["bars"] * paso >= p["time_exit_minutes"]:
                        pend_exit = "tiempo"
            if not hay_sig:
                continue
            s = int(sig[k])
            siguiente = MN[k] + paso
            if s != 0 and (pos is None or pend_exit is not None):
                if pos is not None and s == pos["d"]:
                    continue                                 # sigue en el mismo sentido: no se reabre
                hora_ok = siguiente <= last_entry and siguiente < eod and (win is None or win[0] <= siguiente < win[1])
                if hora_ok:
                    pend_entry = (s, k, (A[k], SL[k], SH[k]))       # (dirección, vela de señal, datos al cierre)
                else:
                    cnt["fuera_de_horario"] += 1
        if pos is not None:
            k = idxs[-1]
            cerrar(C[k], cm.market(C[k], pos["d"], entry=False), T[k], "fin_de_datos", k)
        daily.append({"session": ses[idxs[0]], "pnl": pnl_d, "gross": gross_d, "equity": equity})
    return Result(pd.DataFrame(trades), pd.DataFrame(daily), dict(cnt), capital)
