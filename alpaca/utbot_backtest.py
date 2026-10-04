"""Backtest del indicador "UT Bot Alerts" (stop dinámico de ATR) con futuros CME de Databento.

Réplica del Pine v4:
  nLoss = a * ATR(c)   (ATR de Wilder, como atr() de TradingView)
  stop dinámico: si el precio sigue por encima, sube a max(stop anterior, src - nLoss); si sigue por debajo,
  baja a min(stop anterior, src + nLoss); si cruza, salta al otro lado.
  Buy = src cruza el stop hacia arriba; Sell = cruza hacia abajo. src = cierre (o cierre Heikin Ashi).
Ejecución: la señal se conoce al cierre de la vela y se entra a la apertura de la siguiente (sin mirar el futuro).
Siempre dentro: cada señal contraria da la vuelta a la posición. Coste por lado = COST * precio (comisión + deslizamiento).

Modos:
  24h           siempre dentro, de día y de noche (no vale para Apex: no se puede dormir con posición).
  Apex día      siempre dentro pero cerrado a las 16:50 NY; vuelve a entrar con la siguiente señal tras las 18:00.
  London        señales de 2:00 a 5:00 NY; lo que quede abierto se cierra a las 11:00.
  NY            señales de 9:30 a 11:00 NY; lo que quede abierto se cierra a las 15:55.

Uso:
    python utbot_backtest.py
"""

import numpy as np
import pandas as pd

from crt_backtest import load_5m

COST = 0.00003
DOLLARS = {"NQ": 2, "ES": 5, "GC": 10}       # $ por punto del micro (MNQ, MES, MGC)
MODES = {"24h": None, "Apex día": (18, 16 + 50 / 60, 16 + 50 / 60),
         "London": (2, 5, 11), "NY": (9.5, 11, 15 + 55 / 60)}


def bars(sym, rule):
    df = load_5m(sym)
    if rule == "5min":
        return df
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def signals(df, a, c, ha=False):
    h, l, cl = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev = np.r_[cl[0], cl[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    atr = pd.Series(tr).ewm(alpha=1 / c, adjust=False).mean().to_numpy()
    src = ((df["open"] + df["high"] + df["low"] + df["close"]) / 4).to_numpy() if ha else cl
    n = len(df)
    stop = np.zeros(n)
    sig = np.zeros(n, int)
    for i in range(1, n):
        p, loss = stop[i - 1], a * atr[i]
        if src[i] > p and src[i - 1] > p:
            stop[i] = max(p, src[i] - loss)
        elif src[i] < p and src[i - 1] < p:
            stop[i] = min(p, src[i] + loss)
        else:
            stop[i] = src[i] - loss if src[i] > p else src[i] + loss
        if src[i - 1] <= p and src[i] > stop[i]:
            sig[i] = 1
        elif src[i - 1] >= p and src[i] < stop[i]:
            sig[i] = -1
    return sig


def trades(df, sig, mode):
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    t = df.index
    hrs = (t.hour + t.minute / 60).to_numpy()
    gap = np.r_[False, np.diff(t.asi8) > 30 * 60 * 10**9]       # vela tras el cierre diario o el fin de semana
    win = MODES[mode]
    out, pos, entry, et = [], 0, 0.0, None

    def close(px):
        out.append(dict(day=et, side=pos, pts=pos * (px - entry) - COST * (entry + px)))

    for i in range(1, len(df)):
        h = hrs[i]
        if win is not None:
            s, e, x = win
            if mode == "Apex día":
                can_enter = not (16.75 <= h < 18)
                if pos != 0 and gap[i]:
                    close(c[i - 1])                                 # cerrado al final de la última vela del día
                    pos = 0
                elif pos != 0 and not can_enter:
                    close(o[i])
                    pos = 0
            else:
                can_enter = s <= h < e
                if pos != 0 and (h >= x or h < s or gap[i]):
                    close(c[i - 1] if gap[i] else o[i])
                    pos = 0
        else:
            can_enter = True
        sp = sig[i - 1]
        if sp == 0 or sp == pos:
            continue
        if pos != 0:
            close(o[i])                                             # señal contraria: salir siempre
            pos = 0
        if can_enter:
            pos, entry, et = sp, o[i], t[i]
    return pd.DataFrame(out)


def stats(tr, usd):
    if tr.empty:
        return None
    d = tr["pts"] * usd
    eq = d.cumsum()
    years = (tr["day"].iloc[-1] - tr["day"].iloc[0]).days / 365.25
    g, ls = d[d > 0].sum(), -d[d < 0].sum()
    h = len(d) // 2
    return dict(ops_mes=len(d) / years / 12, acierto=(d > 0).mean(), pf=g / ls if ls else np.inf,
                usd_año=d.sum() / years, max_dd=(eq.cummax() - eq).max(),
                mitad1=d.iloc[:h].sum(), mitad2=d.iloc[h:].sum())


def main():
    rows = []
    for sym in ("NQ", "ES", "GC"):
        for rule in ("5min", "15min", "1h"):
            df = bars(sym, rule)
            for a in (1, 2, 3):
                for ha in (False, True):
                    sig = signals(df, a, 10, ha)
                    for mode in MODES:
                        s = stats(trades(df, sig, mode), DOLLARS[sym])
                        if s:
                            rows.append(dict(mercado=sym, tf=rule, key=a, ha="HA" if ha else "", modo=mode, **s))
            print(f"{sym} {rule} listo", flush=True)
    r = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print("\nResultados por 1 micro (MNQ / MES / MGC), costes incluidos, 2018-2026")
    print(r.round(2).to_string(index=False))
    r.to_csv("utbot_resultados.csv", index=False)


if __name__ == "__main__":
    main()
