"""Barridas de liquidez (liquidity sweeps) en velas de 1 h y 4 h: ¿cuántas veces gira el precio? NQ y oro, 2018 - oct 2026.

Barrida bajista en una temporalidad: la vela supera el último máximo de swing confirmado (fractal de 3 velas a
cada lado) con su mecha y CIERRA por debajo de él. Barrida alcista: espejo con el último mínimo de swing.
Grupos:
  1H        barrida en una vela de 1 h
  4H        barrida en una vela de 4 h (velas de 4 h alineadas como en TradingView: 18, 22, 2, 6, 10, 14 h NY)
  1H + 4H   la vela de 4 h es una barrida y dentro de ella hubo una barrida de 1 h en el mismo sentido
            (se mide desde el cierre de la vela de 4 h)
  ruptura   control: la vela supera el swing y CIERRA más allá (lo contrario de una barrida)
Medida: desde el cierre de la vela de señal, carrera simétrica con velas de 5 min: ¿el precio recorre antes
k · ATR(14) de esa temporalidad A FAVOR del giro, o k · ATR EN CONTRA? (k = 0,5 · 1 · 2). 50 % = azar.
Además, con un stop justo por encima de la mecha de la barrida: ¿llega antes a 1R o 2R que al stop?

Uso:
    python sweep_1h_4h.py
"""

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m


@njit(cache=True)
def race(h5, l5, start, side, e, dist, maxbars):
    """1 si el precio va dist a favor de side antes que dist en contra; 0 si al revés; -1 sin resolver/ambiguo."""
    n = len(h5)
    for q in range(start, min(n, start + maxbars)):
        fav = (l5[q] <= e - dist) if side == -1 else (h5[q] >= e + dist)
        adv = (h5[q] >= e + dist) if side == -1 else (l5[q] <= e - dist)
        if fav and adv:
            return -1
        if fav:
            return 1
        if adv:
            return 0
    return -1


@njit(cache=True)
def rtrade(h5, l5, start, side, e, stop, rr, maxbars):
    n = len(h5)
    risk = abs(e - stop)
    tg = e + side * rr * risk
    for q in range(start, min(n, start + maxbars)):
        if (side == 1 and l5[q] <= stop) or (side == -1 and h5[q] >= stop):
            return 0
        if (side == 1 and h5[q] >= tg) or (side == -1 and l5[q] <= tg):
            return 1
    return -1


def sweeps(b, p=3):
    """Devuelve lista de (i, tipo, lado) en las velas b: tipo 'barrida' o 'ruptura'; lado de la operación de giro."""
    h, l, c = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    n = len(h)
    out = []
    ph, pl = np.nan, np.nan
    for i in range(2 * p, n):
        j = i - p
        if h[j] == h[j - p:j + p + 1].max():
            ph = h[j]
        if l[j] == l[j - p:j + p + 1].min():
            pl = l[j]
        if ph == ph and h[i] > ph:
            out.append((i, "barrida" if c[i] < ph else "ruptura", -1, ph))
            ph = np.nan
        if pl == pl and l[i] < pl:
            out.append((i, "barrida" if c[i] > pl else "ruptura", 1, pl))
            pl = np.nan
    return out


def main():
    pd.set_option("display.width", 220)
    for sym in ("NQ", "GC"):
        d5 = load_5m(sym)
        h5, l5 = d5.high.to_numpy(), d5.low.to_numpy()
        t5 = d5.index
        frames = {"1H": d5.resample("60min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(),
                  "4H": d5.resample("240min", offset="2h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()}
        ev = {}
        for tf, b in frames.items():
            pc = b.close.shift()
            tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
            atr = tr.rolling(14).mean().to_numpy()
            tf_min = 60 if tf == "1H" else 240
            close_t = (b.index + pd.Timedelta(minutes=tf_min)).to_numpy()
            k5 = np.searchsorted(t5.to_numpy(), close_t)          # primera vela de 5 min después del cierre
            ev[tf] = [(b.index[i], kind, s, lvl, b.close.iat[i], b.high.iat[i], b.low.iat[i], atr[i], k5[i])
                      for i, kind, s, lvl in sweeps(b) if np.isfinite(atr[i])]
        # 1H + 4H: barrida de 4 h que contiene una barrida de 1 h del mismo sentido
        s1 = {(t.floor("240min", ambiguous=False) if False else t, s) for t, kind, s, *_ in ev["1H"] if kind == "barrida"}
        b4 = frames["4H"]
        both = []
        one_h = [(t, s) for t, kind, s, *_ in ev["1H"] if kind == "barrida"]
        one_h_t = pd.DatetimeIndex([t for t, _ in one_h])
        one_h_s = np.array([s for _, s in one_h])
        for e in ev["4H"]:
            t, kind, s = e[0], e[1], e[2]
            if kind != "barrida":
                continue
            m = (one_h_t >= t) & (one_h_t < t + pd.Timedelta(hours=4)) & (one_h_s == s)
            if m.any():
                both.append(e)
        groups = {"1H barrida": [e for e in ev["1H"] if e[1] == "barrida"],
                  "1H ruptura (control)": [e for e in ev["1H"] if e[1] == "ruptura"],
                  "4H barrida": [e for e in ev["4H"] if e[1] == "barrida"],
                  "4H ruptura (control)": [e for e in ev["4H"] if e[1] == "ruptura"],
                  "1H + 4H barrida": both}
        rows = []
        for g, E in groups.items():
            r = {"grupo": g, "casos": len(E), "por año": round(len(E) / 8.75)}
            for k in (0.5, 1.0, 2.0):
                res = np.array([race(h5, l5, int(k5i), s, c, k * atr, 2000) for (_, _, s, _, c, hi, lo, atr, k5i) in E])
                ok = res >= 0
                r[f"gira {k} ATR"] = f"{(res[ok] == 1).mean():.0%}"
            for rr in (1.0, 2.0):
                res = np.array([rtrade(h5, l5, int(k5i), s, c, (hi if s == -1 else lo) + (-s) * 0.25, rr, 2000)
                                for (_, _, s, _, c, hi, lo, atr, k5i) in E])
                ok = res >= 0
                r[f"llega a {rr:g}R antes que al stop"] = f"{(res[ok] == 1).mean():.0%}"
            yrs = np.array([e[0].year for e in E])
            res1 = np.array([race(h5, l5, int(k5i), s, c, atr, 2000) for (_, _, s, _, c, hi, lo, atr, k5i) in E])
            for nm_, sel in (("2018-22", yrs < 2023), ("2023-26", yrs >= 2023)):
                x = res1[sel]
                r[f"gira 1 ATR {nm_}"] = f"{(x[x >= 0] == 1).mean():.0%}"
            rows.append(r)
        print(f"\n══════ {sym} ══════  («gira» = el precio va k·ATR en la dirección del giro antes que k·ATR a favor de la barrida; en «ruptura» la operación es contra la ruptura)")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
