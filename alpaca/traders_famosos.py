"""Métodos de traders famosos convertidos en reglas y probados en NQ / MNQ y oro / MGC (sesión 9:30-16:00 NY), 2018 - oct 2026.

1. Larry Williams — ruptura de volatilidad: orden STOP de compra en apertura + k × rango de ayer y de venta en
   apertura − k × rango de ayer (k = 0,25 · 0,4 · 0,6); la primera que entra; stop en la apertura del día o en el
   otro nivel; cierre 16:00.
2. Mark Fisher — ACD: rango de apertura (15 / 30 min); punto «A» = máximo del rango + a × ATR (mínimo − a × ATR para
   cortos), a = 0,05 · 0,1 · 0,15; stop en el otro lado del rango de apertura; cierre 16:00.
3. Linda Raschke — Turtle Soup (intradía): el precio rompe el mínimo de los últimos 20 días (el anterior mínimo de
   20 días tiene ≥ 4 días) y vuelve a cerrar por encima en una vela de 5 min → compra; stop en el mínimo del día;
   espejo en máximos; objetivo 1R · 2R · cierre.
4. Linda Raschke — Holy Grail (15 min): ADX(14) > 30, el precio retrocede hasta la EMA 20 → compra STOP en el máximo
   de esa vela (válida 2 velas), stop en su mínimo; espejo en cortos; objetivo 2R · último extremo de 20 velas · cierre.
5. Tortugas (Richard Dennis) — ruptura de 20 días adaptada a intradía: orden STOP en el máximo / mínimo de 20 días;
   stop 0,5 · 1 ATR diario; cierre 16:00.
ATR = media de 14 días del rango 9:30-16:00. Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Si stop y objetivo caen en la misma vela de 5 min, cuenta el stop. Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python traders_famosos.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m
from nq_intraday_research import build_days


def bracket(B, k0, s, e, sl, tg):
    for q in range(k0, len(B)):
        if (s == 1 and B[q, 2] <= sl) or (s == -1 and B[q, 1] >= sl):
            return min(sl, B[q, 0]) if s == 1 else max(sl, B[q, 0])
        if tg is not None and ((s == 1 and B[q, 1] >= tg) or (s == -1 and B[q, 2] <= tg)):
            return tg
    return B[-1, 3]


def stop_entry(B, k_from, k_to, up_lvl, dn_lvl):
    """Primera vela que toca up_lvl o dn_lvl; devuelve (k, lado, precio) o None (las dos en la misma vela → None)."""
    for k in range(k_from, k_to):
        up, dn = B[k, 1] >= up_lvl, B[k, 2] <= dn_lvl
        if up and dn:
            return None
        if up:
            return k, 1, max(up_lvl, B[k, 0])
        if dn:
            return k, -1, min(dn_lvl, B[k, 0])
    return None


def williams(x, prev, k, stop_mode):
    B = x["rth"]
    R = prev["rth"][:, 1].max() - prev["rth"][:, 2].min()
    op = B[0, 0]
    r = stop_entry(B, 0, 72, op + k * R, op - k * R)
    if r is None:
        return None
    j, s, e = r
    sl = op if stop_mode == "apertura" else (op - k * R if s == 1 else op + k * R)
    if s * (e - sl) <= 0:
        return None
    return s, e, bracket(B, j + 1, s, e, sl, None)


def acd(x, n, a):
    B = x["rth"]
    H, L = B[:n, 1].max(), B[:n, 2].min()
    r = stop_entry(B, n, 72, H + a * x["atr"], L - a * x["atr"])
    if r is None:
        return None
    j, s, e = r
    sl = L if s == 1 else H
    return s, e, bracket(B, j + 1, s, e, sl, None)


def turtle_soup(x, hist, rr):
    B = x["rth"]
    if len(hist) < 20:
        return None
    lows = np.array([h_[:, 2].min() for h_ in hist[-20:]])
    highs = np.array([h_[:, 1].max() for h_ in hist[-20:]])
    L20, H20 = lows.min(), highs.max()
    ageL, ageH = 20 - 1 - lows.argmin(), 20 - 1 - highs.argmax()
    for k in range(1, 72):
        dl, dh = B[:k + 1, 2].min(), B[:k + 1, 1].max()
        if ageL >= 3 and dl < L20 and B[k, 3] > L20:
            s, e, sl = 1, B[k + 1, 0], dl - 0.25
        elif ageH >= 3 and dh > H20 and B[k, 3] < H20:
            s, e, sl = -1, B[k + 1, 0], dh + 0.25
        else:
            continue
        risk = s * (e - sl)
        if risk <= 0:
            return None
        tg = e + s * rr * risk if rr else None
        return s, e, bracket(B, k + 1, s, e, sl, tg)
    return None


def turtles(x, hist, mult):
    B = x["rth"]
    if len(hist) < 20:
        return None
    H20 = max(h_[:, 1].max() for h_ in hist[-20:])
    L20 = min(h_[:, 2].min() for h_ in hist[-20:])
    if not (L20 < B[0, 0] < H20):
        return None
    r = stop_entry(B, 0, 72, H20, L20)
    if r is None:
        return None
    j, s, e = r
    return s, e, bracket(B, j + 1, s, e, e - s * mult * x["atr"], None)


def holy_grail(sym, cost, usd):
    """Holy Grail en velas de 15 min dentro de 9:30-16:00 NY (indicadores con todas las horas)."""
    df = load_5m(sym)
    b = df.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    hi, lo, cl, op = (b[k].to_numpy() for k in ("high", "low", "close", "open"))
    pc = np.r_[cl[0], cl[:-1]]
    tr = np.maximum(hi - lo, np.maximum(abs(hi - pc), abs(lo - pc)))
    upm, dnm = np.r_[0, np.diff(hi)], np.r_[0, -np.diff(lo)]
    pdm = np.where((upm > dnm) & (upm > 0), upm, 0.0)
    ndm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
    w = lambda z: pd.Series(z).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    atr = w(tr)
    pdi, ndi = 100 * w(pdm) / atr, 100 * w(ndm) / atr
    adx = w(100 * abs(pdi - ndi) / np.maximum(pdi + ndi, 1e-9))
    ema = pd.Series(cl).ewm(span=20, adjust=False).mean().to_numpy()
    t = b.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    day = np.array(t.normalize().asi8)
    eod = pd.Series(np.where(hm < 960, np.arange(len(t)), -1)).groupby(day).max().reindex(day).to_numpy()
    out = {m: [] for m in ("2R", "extremo 20 velas", "cierre")}
    for tgt_mode in out:
        i, n = 30, len(cl)
        while i < n - 3:
            if not (570 <= hm[i] <= 900) or adx[i] <= 30:
                i += 1
                continue
            s = 1 if pdi[i] > ndi[i] else -1
            touch = (lo[i] <= ema[i] <= hi[i])
            if not touch:
                i += 1
                continue
            lvl, sl = (hi[i], lo[i]) if s == 1 else (lo[i], hi[i])
            done = False
            for j in (i + 1, i + 2):
                if j >= n or day[j] != day[i]:
                    break
                if (s == 1 and hi[j] > lvl) or (s == -1 and lo[j] < lvl):
                    e = max(lvl, op[j]) if s == 1 else min(lvl, op[j])
                    risk = s * (e - sl)
                    if risk <= 0:
                        break
                    tg = (e + s * 2 * risk if tgt_mode == "2R" else (hi[i - 20:i].max() if s == 1 else lo[i - 20:i].min())
                          if tgt_mode == "extremo 20 velas" else None)
                    if tg is not None and s * (tg - e) <= 0:
                        break
                    end = eod[j]
                    px = cl[end]
                    q_end = end
                    for q in range(j + 1, end + 1):
                        if (s == 1 and lo[q] <= sl) or (s == -1 and hi[q] >= sl):
                            px, q_end = sl, q
                            break
                        if tg is not None and ((s == 1 and hi[q] >= tg) or (s == -1 and lo[q] <= tg)):
                            px, q_end = tg, q
                            break
                    out[tgt_mode].append((t[j].year, (s * (px - e) - cost) * usd))
                    i = q_end + 1
                    done = True
                    break
            if not done:
                i += 1
    return out


def summarize(rows, sym, metodo, variante, res):
    R = pd.DataFrame(res, columns=["y", "u"])
    if len(R) < 60:
        return
    d, v = R[R.y < 2023].u, R[R.y >= 2023].u
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = R.u.cumsum()
    rows.append(dict(activo=sym, metodo=metodo, variante=variante, ops_año=round(len(R) / 8.75), acierto=f"{(R.u > 0).mean():.0%}",
                     dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                     peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days = build_days(sym)
        run = lambda f: [(pd.Timestamp(days[i]["d"]).year, (r[0] * (r[2] - r[1]) - cost) * usd)
                         for i in range(1, len(days)) for r in [f(i)] if r is not None]
        for k, sm in itertools.product((0.25, 0.4, 0.6), ("apertura", "otro nivel")):
            summarize(rows, sym, "Larry Williams · volatilidad", f"k={k} · stop {sm}", run(lambda i: williams(days[i], days[i - 1], k, sm)))
        for n, a in itertools.product((3, 6), (0.05, 0.1, 0.15)):
            summarize(rows, sym, "Mark Fisher · ACD", f"rango {n * 5} min · A={a} ATR", run(lambda i: acd(days[i], n, a)))
        hist = [x["rth"] for x in days]
        for rr in (1.0, 2.0, 0.0):
            summarize(rows, sym, "Raschke · Turtle Soup", f"obj {rr:g}R" if rr else "obj cierre",
                      run(lambda i: turtle_soup(days[i], hist[max(0, i - 20):i], rr)))
        for m in (0.5, 1.0):
            summarize(rows, sym, "Tortugas · 20 días", f"stop {m} ATR", run(lambda i: turtles(days[i], hist[max(0, i - 20):i], m)))
        for tg, res in holy_grail(sym, cost, usd).items():
            summarize(rows, sym, "Raschke · Holy Grail 15m", f"obj {tg}", res)
        print(sym, "listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/traders_famosos.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(R.groupby(["activo", "metodo"], sort=False).apply(lambda g: pd.Series({"variantes": len(g), "% ganan ambos": both(g),
          "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    print()
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
