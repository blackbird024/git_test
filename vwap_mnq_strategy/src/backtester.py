"""Motor de backtest propio, cronológico, vela a vela.

Por qué propio y no una librería: hace falta (1) decidir en velas de 15 min y resolver stops/targets con las
sub-velas de 1 min, (2) reiniciar todo en cada sesión sin posiciones overnight, (3) costes y reglas de riesgo del
MNQ exactos y auditables. Un motor pequeño y probado con escenarios artificiales es más fácil de verificar.

Secuencia en cada vela k de una sesión:
  1. Apertura de k: se ejecutan las órdenes decididas al cierre de k-1 (salida, entrada o giro).
  2. Si k empieza a la hora de cierre forzado: se cierra a la apertura.
  3. Durante k: stop/target/trailing con las sub-velas, en orden cronológico.
  4. Cierre de k: se actualiza trailing y time stop y se calculan señales -> órdenes para la apertura de k+1.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .execution import CostModel, check_exit_subbar
from .risk_manager import RiskManager
from .signals import filtros, señales, ventana_horaria


def _min(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


@dataclass
class Resultado:
    trades: pd.DataFrame
    daily: pd.DataFrame          # una fila por sesión válida del periodo: pnl neto, bruto, equity
    contadores: dict
    capital_inicial: float


def cost_model(cfg: dict, adverso: bool = False) -> CostModel:
    c, i = cfg["costs"], cfg["instrument"]
    return CostModel(tick=i["tick_size"], point_value=i["point_value"], commission_per_side=c["commission_per_side"],
                     slippage_ticks=c["slippage_ticks_adverse"] if adverso else c["slippage_ticks"],
                     target_requires_through=c["target_requires_through"])


def risk_manager(cfg: dict) -> RiskManager:
    r, i = cfg["risk"], cfg["instrument"]
    return RiskManager(sizing=r["sizing"], risk_pct=r["risk_pct"], fixed_contracts=r["fixed_contracts"],
                       max_contracts=r["max_contracts"], min_contracts=i["min_contracts"], point_value=i["point_value"],
                       daily_loss_limit_pct=r["daily_loss_limit_pct"], max_trades_per_session=r["max_trades_per_session"],
                       pause_after_losses=r["pause_after_losses"])


def seleccionar(b: pd.DataFrame, desde=None, hasta=None) -> np.ndarray:
    ses = pd.to_datetime(b.session.astype(str))
    m = b.session_valid.to_numpy(bool).copy()
    if desde is not None:
        m &= (ses >= pd.Timestamp(desde)).to_numpy()
    if hasta is not None:
        m &= (ses <= pd.Timestamp(hasta)).to_numpy()
    return m


def run(b: pd.DataFrame, sub: dict, cfg: dict, desde=None, hasta=None, sig_override: np.ndarray | None = None,
        adverso: bool = False) -> Resultado:
    st, ex = cfg["strategy"], cfg["strategy"]["exits"]
    pv = cfg["instrument"]["point_value"]
    cm, rm = cost_model(cfg, adverso), risk_manager(cfg)
    sig = señales(b, "vwap", st["entry_mode"]) if sig_override is None else sig_override
    L, S = filtros(b, cfg)
    win = ventana_horaria(cfg)
    last_entry, eod, paso = _min(st["last_entry_time"]), _min(st["eod_exit_time"]), int(cfg["bars"]["minutes"])
    sl_k, tp_r, trail = ex["sl_atr_mult"], ex["tp_r"], ex["trailing_atr_mult"]
    dist_k = sl_k if sl_k is not None else ex["risk_atr_mult_if_no_stop"]
    O, C, A = b.open.to_numpy(), b.close.to_numpy(), b.atr.to_numpy()
    MN, I0, I1 = b.start_ny_min.to_numpy(), b.i0.to_numpy(), b.i1.to_numpy()
    T = b.start.dt.tz_localize(None).to_numpy()              # UTC sin zona (igual que las sub-velas)
    so, sh, sl_, st_ = sub["open"], sub["high"], sub["low"], sub["time"]
    ses_arr = b.session.to_numpy()
    sel = np.flatnonzero(seleccionar(b, desde, hasta))
    capital = float(cfg["risk"]["initial_capital"])
    equity = capital
    trades, daily, cont = [], [], Counter()

    if len(sel) == 0:
        return Resultado(pd.DataFrame(), pd.DataFrame(columns=["session", "pnl", "gross", "equity"]), {}, capital)
    s_sel = ses_arr[sel]
    cortes = np.flatnonzero(s_sel[1:] != s_sel[:-1]) + 1
    for idxs in np.split(sel, cortes):
        rm.new_session(equity)
        pos, pend = None, None
        pnl_dia, bruto_dia = 0.0, 0.0

        def cerrar(p, bruto_px, fill_px, t, motivo, k):
            nonlocal equity, pnl_dia, bruto_dia
            d, q = p["d"], p["qty"]
            gross = (bruto_px - p["raw_entry"]) * d * q * pv
            net = (fill_px - p["entry"]) * d * q * pv - cm.commission(q)
            riesgo = q * p["dist"] * pv
            equity += net
            pnl_dia += net
            bruto_dia += gross
            rm.on_close(net)
            trades.append({"session": ses_arr[k], "direction": d, "qty": q, "entry_time": p["t"], "entry_price": p["entry"],
                           "raw_entry": p["raw_entry"], "exit_time": t, "exit_price": fill_px, "raw_exit": bruto_px,
                           "stop_initial": p["stop0"], "target": p["target"], "exit_reason": motivo,
                           "gross_pnl": gross, "costs": gross - net, "net_pnl": net, "risk_usd": riesgo,
                           "r_net": net / riesgo, "r_gross": gross / riesgo, "mae_pts": p["mae"], "mfe_pts": p["mfe"],
                           "bars_held": p["bars"], "entry_ny_min": p["mn"], "atr_entry": p["atr"]})

        def abrir(d, k, atr_dec):
            nonlocal pos
            ok, porque = rm.can_open()
            if not ok:
                cont[porque] += 1
                return
            if not np.isfinite(atr_dec) or atr_dec <= 0:
                cont["sin_atr"] += 1
                return
            dist = dist_k * atr_dec
            q = rm.size(equity, dist)
            if q < 1:
                cont["tamano_menor_que_minimo"] += 1
                return
            fill = cm.market(O[k], d, is_entry=True)
            stop = fill - d * dist if sl_k is not None else None
            target = fill + d * tp_r * dist if tp_r is not None else None
            pos = {"d": d, "qty": q, "entry": fill, "raw_entry": O[k], "t": T[k], "dist": dist, "stop": stop,
                   "stop0": stop, "target": target, "mae": 0.0, "mfe": 0.0, "bars": 0, "best": fill, "mn": MN[k],
                   "atr": atr_dec}
            rm.on_open()
            cont["entradas"] += 1

        for n_k, k in enumerate(idxs):
            # 1) órdenes en la apertura de k
            if pend is not None:
                tipo, d_new, atr_dec, motivo = pend
                if pos is not None and tipo in ("exit", "reverse"):
                    cerrar(pos, O[k], cm.market(O[k], pos["d"], is_entry=False), T[k], motivo, k)
                    pos = None
                if pos is None and tipo in ("entry", "reverse"):
                    abrir(d_new, k, atr_dec)
                pend = None
            # 2) cierre forzado de fin de sesión
            if MN[k] >= eod:
                if pos is not None:
                    cerrar(pos, O[k], cm.market(O[k], pos["d"], is_entry=False), T[k], "fin_de_sesion", k)
                    pos = None
                continue
            # 3) gestión dentro de la vela con las sub-velas
            if pos is not None:
                d = pos["d"]
                for j in range(I0[k], I1[k] + 1):
                    pos["mfe"] = max(pos["mfe"], (sh[j] - pos["entry"]) if d == 1 else (pos["entry"] - sl_[j]))
                    pos["mae"] = max(pos["mae"], (pos["entry"] - sl_[j]) if d == 1 else (sh[j] - pos["entry"]))
                    r = check_exit_subbar(so[j], sh[j], sl_[j], d, pos["stop"], pos["target"], cm)
                    if r is not None:
                        motivo = "trailing" if (r[0] == "stop" and pos["stop"] != pos["stop0"]) else r[0]
                        cerrar(pos, r[1], r[2], st_[j], motivo, k)
                        pos = None
                        break
            # 4) cierre de k: gestión y señales para la apertura de k+1
            siguiente = MN[k] + paso
            hay_siguiente = n_k + 1 < len(idxs)
            if pos is not None:
                pos["bars"] += 1
                if trail is not None and np.isfinite(A[k]):
                    pos["best"] = max(pos["best"], C[k]) if pos["d"] == 1 else min(pos["best"], C[k])
                    cand = pos["best"] - pos["d"] * trail * A[k]
                    if pos["stop"] is None or (cand - pos["stop"]) * pos["d"] > 0:
                        pos["stop"] = cand
                if ex["time_stop_bars"] is not None and pos["bars"] >= ex["time_stop_bars"] and hay_siguiente:
                    pend = ("exit", 0, A[k], "time_stop")
            if not hay_siguiente:
                continue
            s = int(sig[k])
            if s == 0:
                continue
            permite = (L[k] if s == 1 else S[k])
            hora_ok = siguiente <= last_entry and siguiente < eod and (win is None or win[0] <= siguiente < win[1])
            if pos is not None:
                if s == -pos["d"] and ex["opposite_signal"]:
                    girar = ex["reverse_on_opposite"] and permite and hora_ok
                    pend = ("reverse" if girar else "exit", s, A[k], "senal_contraria")
            elif pend is None:
                if permite and hora_ok:
                    pend = ("entry", s, A[k], "")
                else:
                    cont["senal_filtrada"] += 1
        if pos is not None:                                   # no debería ocurrir (cierre forzado)
            k = idxs[-1]
            cerrar(pos, C[k], cm.market(C[k], pos["d"], is_entry=False), T[k], "fin_de_datos", k)
        daily.append({"session": ses_arr[idxs[0]], "pnl": pnl_dia, "gross": bruto_dia, "equity": equity})

    return Resultado(pd.DataFrame(trades), pd.DataFrame(daily), dict(cont), capital)


def buy_hold_intradia(b: pd.DataFrame, cfg: dict, desde=None, hasta=None) -> pd.DataFrame:
    """Referencia: 1 contrato largo de la apertura (09:30) a la vela de cierre forzado, cada sesión, con costes."""
    cm = cost_model(cfg)
    pv, eod = cfg["instrument"]["point_value"], _min(cfg["strategy"]["eod_exit_time"])
    x = b[seleccionar(b, desde, hasta)]
    filas = []
    for ses, g in x.groupby("session"):
        ini, fin = g.iloc[0], g[g.start_ny_min >= eod]
        if fin.empty:
            continue
        e, s = cm.market(ini.open, 1, True), cm.market(fin.iloc[0].open, 1, False)
        filas.append({"session": ses, "net_pnl": (s - e) * pv - cm.commission(1), "gross_pnl": (fin.iloc[0].open - ini.open) * pv})
    return pd.DataFrame(filas)
