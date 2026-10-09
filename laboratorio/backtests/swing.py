"""Simulador swing diario (solo largos, una posición, 100 % del capital como máximo, sin apalancamiento).

Ejecución:
  mode="next_open": la señal del cierre de t se ejecuta en la apertura de t+1 (implementable sin vigilar el cierre).
  mode="close":     se ejecuta al cierre de t (requiere orden al cierre o decidir minutos antes: aproximación).
Stop inicial = precio de entrada − stop_dist (conocido en t). Se comprueba con el mínimo diario: si la apertura ya está
por debajo → salida en la apertura (hueco); si no, al stop con el deslizamiento. Salidas por regla y por tiempo se
ejecutan con el mismo modo que la entrada.
Costes: `pct_side` (spread + deslizamiento) por lado sobre el nominal y `fixed` por operación y lado en la divisa del capital.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SwingCost:
    pct_side: float = 0.0005
    fixed: float = 0.0
    capital: float = 10_000.0


def simulate(d: pd.DataFrame, sig: pd.DataFrame, cost: SwingCost, mode="next_open"):
    O, H, L, C = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
    E, X, SD = sig["entry"].to_numpy(), sig["exit"].to_numpy(), sig["stop_dist"].to_numpy()
    MD = sig["max_days"].iloc[0] if len(sig) else None
    MD = None if MD is None or pd.isna(MD) else int(MD)
    idx = d.index
    n = len(d)
    trades = []
    pos = pend_in = pend_out = False
    entry_px = stop = np.nan
    ei = si = 0

    def close_trade(i, px, why):
        trades.append((idx[ei], idx[i], entry_px, px, why, i - ei))

    for i in range(n):
        # 1) órdenes pendientes en la apertura (modo next_open)
        if pend_out:
            close_trade(i, O[i], pend_out); pos = pend_out = False
        if pend_in:
            pos, entry_px, ei, pend_in = True, O[i], i, False
            stop = entry_px - SD[si] if not np.isnan(SD[si]) else np.nan
        # 2) stop durante la sesión (no el mismo día si se entró al cierre)
        if pos and not np.isnan(stop) and not (mode == "close" and i == ei):
            if i > ei and O[i] <= stop:
                close_trade(i, O[i], "stop_hueco"); pos = False
            elif L[i] <= stop:
                close_trade(i, stop * (1 - cost.pct_side), "stop"); pos = False
        exited_today = not pos and len(trades) and trades[-1][1] == idx[i]
        # 3) salidas por regla o tiempo, decididas al cierre
        if pos and not (mode == "close" and i == ei):
            why = "regla" if X[i] else ("tiempo" if MD is not None and i - ei >= MD else None)
            if why:
                if mode == "close":
                    close_trade(i, C[i], why); pos = False; exited_today = True
                else:
                    pend_out = why
        # 4) entradas decididas al cierre
        if not pos and not pend_in and not exited_today and E[i] and i < n - 1:
            if mode == "close":
                pos, entry_px, ei = True, C[i], i
                stop = entry_px - SD[i] if not np.isnan(SD[i]) else np.nan
            else:
                pend_in, si = True, i
    if pos:
        close_trade(n - 1, C[n - 1], "abierta_fin_datos")
    t = pd.DataFrame(trades, columns=["entrada", "salida", "px_entrada", "px_salida", "motivo", "dias"])
    if len(t):
        gross = t["px_salida"] / t["px_entrada"] - 1
        t["ret"] = gross - 2 * cost.pct_side - 2 * cost.fixed / cost.capital
    return t


def equity(d: pd.DataFrame, t: pd.DataFrame, start=None, end=None):
    """Curva de capital diaria (1 = inicio) suponiendo 100 % invertido durante cada operación y efectivo al 0 % fuera.
    Las rentabilidades de cada operación se reparten entre sus días a precio de cierre (marcado a mercado)."""
    c = d["close"]
    r = pd.Series(0.0, index=d.index)
    inpos = pd.Series(False, index=d.index)
    for _, x in t.iterrows():
        seg = c.loc[x["entrada"]:x["salida"]]
        if len(seg) < 2:
            r.loc[x["salida"]] += x["ret"]
            continue
        path = seg.copy()
        path.iloc[0] = x["px_entrada"]
        path.iloc[-1] = x["px_salida"]
        dr = path.pct_change().iloc[1:]
        adj = (1 + x["ret"]) / (1 + (x["px_salida"] / x["px_entrada"] - 1))     # costes repartidos al final
        dr.iloc[-1] = (1 + dr.iloc[-1]) * adj - 1
        r.loc[dr.index] += dr
        inpos.loc[seg.index[1:]] = True
    if start is not None:
        r, inpos = r[r.index >= start], inpos[inpos.index >= start]
    if end is not None:
        r, inpos = r[r.index <= end], inpos[inpos.index <= end]
    return (1 + r).cumprod(), inpos


def stats(eq: pd.Series, inpos: pd.Series, t: pd.DataFrame):
    yrs = len(eq) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    dr = eq.pct_change().dropna()
    sd = dr.std()
    down = np.sqrt((dr.clip(upper=0) ** 2).mean())
    out = dict(cagr=cagr, dd_max_pct=dd, mar=cagr / -dd if dd < 0 else np.nan,
               sharpe=dr.mean() / sd * np.sqrt(252) if sd > 0 else np.nan,
               sortino=dr.mean() / down * np.sqrt(252) if down > 0 else np.nan, exposicion=inpos.mean())
    if len(t):
        r = t["ret"]
        out.update(n=len(t), acierto=(r > 0).mean(), pf=r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf,
                   esperanza_pct=r.mean(), dur_mediana=t["dias"].median(),
                   pct_en_1_4_semanas=((t["dias"] >= 5) & (t["dias"] <= 21)).mean(),   # 1-4 semanas = 5-21 sesiones
                   top5_pct=r.sort_values(ascending=False).head(5).sum() / r.sum() if r.sum() > 0 else np.nan)
    else:
        out.update(n=0)
    return out
