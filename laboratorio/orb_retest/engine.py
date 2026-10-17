"""Recorre las sesiones y produce (a) operaciones normalizadas a 1 contrato con resultado neto en R y (b) un registro
por sesión con el motivo de cada día sin operación."""
import numpy as np
import pandas as pd

from .config import Config
from .execution import contracts_for, cost_usd_per_contract, simulate
from .signals import detect


def session_ok(s, cfg: Config):
    """Motivo de exclusión de la sesión ANTES de mirar precios posteriores al rango (o None si es válida)."""
    if s.close_min < 150:
        return "sesion_demasiado_corta"
    return None


def run(S, cfg: Config):
    """S: lista de data.loaders.Session. Devuelve (trades, days)."""
    st, c = cfg.strategy, cfg.costs
    trades, days = [], []
    pv = c.point_value
    for s in S:
        d = dict(date=s.date, roll_week=s.roll_week, half_day=s.close_min < 390)
        why = session_ok(s, cfg)
        if why:
            days.append(dict(d, motivo=why))
            continue
        sig, why = detect(s.m, s.close_min, st, c.tick)
        if sig is None:
            days.append(dict(d, motivo=why))
            continue
        tr, why = simulate(sig, s.m, s.close_min, st, c)
        if tr is None:
            days.append(dict(d, motivo=why, side=sig.side))
            continue
        cost1 = cost_usd_per_contract(c)
        net1 = tr.gross_pts * pv - cost1
        risk1 = tr.r_pts * pv
        est_r = sig.side * (sig.signal_close - tr.sl)          # conocido al cierre de la vela de señal
        row = dict(d, **tr.as_dict(), orh=sig.orh, orl=sig.orl, or_width=sig.orh - sig.orl,
                   breakout_bar=sig.breakout_bar, retest_bar=sig.retest_bar, signal_k=sig.signal_k,
                   est_r_pts=est_r, net_usd_1c=net1, risk_usd_1c=risk1, R=net1 / risk1,
                   R_gross=tr.gross_pts / tr.r_pts, minutes_in_trade=tr.exit_k - tr.entry_k,
                   entry_time=_hhmm(tr.entry_k), exit_time=_hhmm(tr.exit_k))
        trades.append(row)
        days.append(dict(d, motivo="operacion", side=sig.side))
    t = pd.DataFrame(trades)
    dd = pd.DataFrame(days)
    return t, dd


def _hhmm(k):
    k = int(k) + 570
    return f"{k // 60:02d}:{k % 60:02d}"


def size_and_account(t: pd.DataFrame, cfg: Config):
    """Aplica el tamaño por riesgo y las reglas de cuenta (límite diario, drawdown máximo). Devuelve las operaciones con
    contratos y PnL en USD, y la curva de saldo diaria implícita. Si un límite se alcanza, no se abren más operaciones."""
    r, c = cfg.risk, cfg.costs
    bal = r.initial_capital
    peak_close = bal
    floor = bal - r.max_drawdown if r.max_drawdown > 0 else -np.inf
    out = []
    stopped = None
    for _, x in t.sort_values("date").iterrows():
        if stopped:
            out.append(dict(x, contracts=0, pnl_usd=0.0, skipped=stopped))
            continue
        budget = r.risk_pct / 100 * bal if r.risk_pct > 0 else r.risk_usd
        q = contracts_for(budget, x.est_r_pts, c, r.max_contracts)
        if q < 1:
            out.append(dict(x, contracts=0, pnl_usd=0.0, skipped="no_cabe_un_contrato"))
            continue
        pnl = q * x.net_usd_1c
        # Con una sola operación por sesión, el límite de pérdida diaria no puede impedir ninguna entrada: solo se
        # registra si una operación lo supera (p. ej. por un hueco).
        breach = bool(r.daily_loss_limit > 0 and pnl < -r.daily_loss_limit)
        bal += pnl
        if r.drawdown_type == "trailing_cierre" and r.max_drawdown > 0:
            peak_close = max(peak_close, bal)
            floor = max(floor, min(peak_close - r.max_drawdown, r.initial_capital))
        out.append(dict(x, contracts=q, pnl_usd=pnl, balance=bal, skipped="", supera_limite_diario=breach))
        if bal <= floor:
            stopped = "limite_drawdown_alcanzado"
    return pd.DataFrame(out)
