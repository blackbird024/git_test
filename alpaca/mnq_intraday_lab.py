"""Laboratorio de estrategias intradía para MNQ (y ES como control) con futuros CME de Databento, 2018-2026.

Todas cierran el mismo día (compatibles con Apex). Sesión regular 9:30-16:00 NY, velas de 5 minutos.
Coste por operación ida y vuelta: 1 punto de NQ/ES (comisión del micro + 1 tick de deslizamiento por lado).
Muestra de desarrollo 2018-2022 y muestra de validación 2023-2026: una estrategia solo vale si gana en las dos.

Estrategias (todas publicadas, no inventadas sobre estos datos):
  noise    "Beat the Market" (Zarattini, Aziz, Barbon 2024): bandas de "ruido" según el movimiento medio a cada hora
           de los últimos 14 días; largo si el precio sale por arriba, corto si sale por abajo, revisando cada 30 min;
           salida si vuelve dentro de la banda / cruza la media del día, y cierre a las 16:00.
  orb      Rango de apertura (Zarattini 2023): dirección de la primera vela de N minutos, stop en el otro extremo,
           objetivo 10R o cierre del día. También la ruptura clásica del máximo/mínimo del rango.
  mom      Momentum intradía (Gao, Han, Li, Zhou 2018): el signo de la primera media hora (desde el cierre
           anterior hasta las 10:00) decide la última media hora (15:30-16:00).
  gap      Cierre de hueco: si abre lejos del cierre anterior, ir hacia él (stop del mismo tamaño, salida a las 11:00).

Uso:
    python mnq_intraday_lab.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m

COST = 1.0                 # puntos ida y vuelta
USD = 2                    # $ por punto en MNQ y en... MES es 5 $/punto, pero el resultado se da en puntos ×2 para comparar
SPLIT = 2023


def rth_days(sym):
    df = load_5m(sym)
    t = df.index
    m = (t.hour * 60 + t.minute)
    df = df[(m >= 570) & (m < 960)].copy()                      # velas que empiezan entre 9:30 y 15:55
    df["k"] = ((df.index.hour * 60 + df.index.minute) - 570) // 5
    days = []
    for d, g in df.groupby(df.index.date):
        if len(g) == 78 and g["k"].iloc[0] == 0:
            days.append((d, g[["open", "high", "low", "close"]].to_numpy()))
    return days


# ───────────────────────── estrategias: cada una devuelve lista de (día, puntos) ─────────────────────────

def noise(days, lookback=14, step=6, trail=True, band_mult=1.0):
    out = []
    moves = np.array([np.abs(b[:, 3] / b[0, 0] - 1) for _, b in days])      # (días, 78)
    for i in range(lookback + 1, len(days)):
        d, b = days[i]
        prev_close = days[i - 1][1][-1, 3]
        sigma = moves[i - lookback:i].mean(axis=0) * band_mult
        o = b[0, 0]
        ub = max(o, prev_close) * (1 + sigma)
        lb = min(o, prev_close) * (1 - sigma)
        typ = (b[:, 1] + b[:, 2] + b[:, 3]) / 3
        twap = np.cumsum(typ) / np.arange(1, 79)                           # sin volumen: media del día
        pos, entry, pnl = 0, 0.0, 0.0
        for k in range(step - 1, 77, step):                                 # decide al cierre de 10:00, 10:30, ...
            c = b[k, 3]
            px = b[k + 1, 0]                                                # ejecuta a la apertura siguiente
            if pos == 1 and c < (max(ub[k], twap[k]) if trail else ub[k]):
                pnl += px - entry - COST; pos = 0
            elif pos == -1 and c > (min(lb[k], twap[k]) if trail else lb[k]):
                pnl += entry - px - COST; pos = 0
            if pos == 0 and c > ub[k]:
                pos, entry = 1, px
            elif pos == 0 and c < lb[k]:
                pos, entry = -1, px
        if pos:
            pnl += pos * (b[-1, 3] - entry) - COST
        if pnl != 0:
            out.append((d, pnl))
    return out


def orb(days, n_bars=1, mode="dir", target_r=10):
    out = []
    for d, b in days:
        hi, lo = b[:n_bars, 1].max(), b[:n_bars, 2].min()
        if mode == "dir":
            o, c = b[0, 0], b[n_bars - 1, 3]
            if c == o:
                continue
            side = 1 if c > o else -1
            entry, k0 = b[n_bars, 0], n_bars
        else:                                                               # ruptura del máximo o mínimo
            side = 0
            for k in range(n_bars, 78):
                if b[k, 1] > hi:
                    side, entry, k0 = 1, hi, k; break
                if b[k, 2] < lo:
                    side, entry, k0 = -1, lo, k; break
            if not side:
                continue
        stop = lo if side == 1 else hi
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        tgt = entry + side * target_r * risk
        px = b[-1, 3]
        for k in range(k0, 78):
            if (side == 1 and b[k, 2] <= stop) or (side == -1 and b[k, 1] >= stop):
                px = stop; break
            if (side == 1 and b[k, 1] >= tgt) or (side == -1 and b[k, 2] <= tgt):
                px = tgt; break
        out.append((d, side * (px - entry) - COST))
    return out


def mom(days, filt=0.0):
    out = []
    for i in range(1, len(days)):
        d, b = days[i]
        r1 = b[5, 3] / days[i - 1][1][-1, 3] - 1                            # cierre anterior → 10:00
        if abs(r1) <= filt:
            continue
        side = 1 if r1 > 0 else -1
        out.append((d, side * (b[-1, 3] - b[72, 0]) - COST))                # 15:30 → 16:00
    return out


def gap(days, g=0.005, exit_k=18):
    out = []
    for i in range(1, len(days)):
        d, b = days[i]
        pc, o = days[i - 1][1][-1, 3], b[0, 0]
        gp = o / pc - 1
        if abs(gp) < g:
            continue
        side = -1 if gp > 0 else 1
        stop = o - side * abs(o - pc)
        px = b[exit_k - 1, 3]
        for k in range(exit_k):
            if (side == 1 and b[k, 2] <= stop) or (side == -1 and b[k, 1] >= stop):
                px = stop; break
            if (side == 1 and b[k, 1] >= pc) or (side == -1 and b[k, 2] <= pc):
                px = pc; break
        out.append((d, side * (px - o) - COST))
    return out


# ───────────────────────── evaluación ─────────────────────────

def evaluate(trades):
    t = pd.DataFrame(trades, columns=["day", "pts"])
    if t.empty:
        return None
    t["year"] = pd.to_datetime(t["day"]).dt.year
    usd = t["pts"] * USD
    eq = usd.cumsum()
    yrs = (pd.to_datetime(t["day"].iloc[-1]) - pd.to_datetime(t["day"].iloc[0])).days / 365.25
    ins, oos = t[t.year < SPLIT], t[t.year >= SPLIT]
    yi = max(len(set(ins.year)), 1)
    yo = max((pd.to_datetime(oos.day.iloc[-1]) - pd.to_datetime(oos.day.iloc[0])).days / 365.25, 0.1) if len(oos) else 1
    g, l = usd[usd > 0].sum(), -usd[usd < 0].sum()
    by_year = t.groupby("year")["pts"].sum()
    return dict(ops_mes=len(t) / yrs / 12, acierto=(usd > 0).mean(), pf=g / l if l else np.inf,
                usd_año=usd.sum() / yrs, dd_max=(eq.cummax() - eq).max(),
                desarrollo_año=ins.pts.sum() * USD / yi, validacion_año=oos.pts.sum() * USD / yo,
                años_pos=f"{(by_year > 0).sum()}/{len(by_year)}")


def main():
    tests = {
        "noise 30min + media": lambda D: noise(D),
        "noise 30min sin media": lambda D: noise(D, trail=False),
        "noise 60min + media": lambda D: noise(D, step=12),
        "noise 30min banda x1.5": lambda D: noise(D, band_mult=1.5),
        "ORB 5m dirección 10R": lambda D: orb(D, 1),
        "ORB 15m dirección 10R": lambda D: orb(D, 3),
        "ORB 30m dirección 10R": lambda D: orb(D, 6),
        "ORB 15m ruptura 10R": lambda D: orb(D, 3, "break"),
        "ORB 30m ruptura 10R": lambda D: orb(D, 6, "break"),
        "ORB 30m ruptura 2R": lambda D: orb(D, 6, "break", 2),
        "momentum 1ª→última media hora": lambda D: mom(D),
        "momentum filtro 0,25%": lambda D: mom(D, 0.0025),
        "hueco 0,5% hacia cierre": lambda D: gap(D),
        "hueco 1% hacia cierre": lambda D: gap(D, 0.01),
    }
    pd.set_option("display.width", 220)
    for sym in ("NQ", "ES"):
        days = rth_days(sym)
        rows = []
        for name, f in tests.items():
            s = evaluate(f(days))
            if s:
                rows.append(dict(estrategia=name, **s))
        print(f"\n=== {sym}: resultado por 1 micro en $ de MNQ (2 $/punto), costes incluidos, {days[0][0]} a {days[-1][0]} ===")
        print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
