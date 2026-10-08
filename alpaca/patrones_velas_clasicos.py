"""Patrones de velas japonesas CLÁSICOS por sí solos (sin niveles ni medias), NQ / MNQ y oro / MGC, 2018 - oct 2026.

Patrones (alcista; el bajista es el espejo):
  martillo        mecha inferior ≥ 2 × cuerpo y mecha superior ≤ cuerpo (cualquier color)
  envolvente      vela alcista cuyo cuerpo envuelve el cuerpo de la vela bajista anterior
  harami          vela alcista con el cuerpo dentro del cuerpo de la bajista anterior
  estrella        estrella de la mañana: bajista grande, vela de cuerpo pequeño, alcista que cierra sobre el medio de la 1.ª
  tres soldados   tres velas alcistas seguidas, cada una cierra más arriba y con cuerpo ≥ 50 % de su rango
  marubozu        vela alcista con cuerpo ≥ 90 % de su rango
  pinzas          pinzas de suelo: dos mínimos casi iguales (≤ 5 % del rango), la 1.ª bajista y la 2.ª alcista
Filtro de tamaño: todas · solo velas grandes (rango de la vela ≥ ATR(14) de esa temporalidad).
Dirección: la clásica (martillo, envolvente, harami, estrella, pinzas = giro; soldados, marubozu = continuación)
           y la CONTRARIA como control.
Temporalidades 5 min, 15 min, 1 h, 4 h: señales con la vela cerrada entre 3:00 y 15:00 NY; entrada en la apertura
de la siguiente vela de 5 min; stop en el extremo del patrón; objetivo 1R, 2R o cierre; cierre forzoso 16:00 NY.
Diario (sesión Globex): con el patrón de ayer, entrada a las 9:30 NY en su dirección y cierre 16:00 NY (sin stop).
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). Máximo una operación abierta a la vez.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python patrones_velas_clasicos.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

REVERSAL = ("martillo", "envolvente", "harami", "estrella", "pinzas")
PATS = REVERSAL + ("tres soldados", "marubozu")


def patterns(b):
    """Devuelve {patrón: array de lado (+1 alcista, -1 bajista, 0 nada)} para las velas b."""
    o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
    rng = h - l
    body = np.abs(c - o)
    up_w = h - np.maximum(o, c)
    lo_w = np.minimum(o, c) - l
    bull, bear = c > o, c < o
    sh = lambda x, k=1: np.r_[np.full(k, np.nan), x[:-k]]
    o1, c1, h1, l1, r1, b1 = sh(o), sh(c), sh(h), sh(l), sh(rng), sh(body)
    o2, c2, b2, r2 = sh(o, 2), sh(c, 2), sh(body, 2), sh(rng, 2)
    bull1, bear1 = sh(bull.astype(float)) == 1, sh(bear.astype(float)) == 1
    out = {}
    ok = rng > 0
    out["martillo"] = np.where(ok & (lo_w >= 2 * body) & (up_w <= body) & (body > 0), 1,
                               np.where(ok & (up_w >= 2 * body) & (lo_w <= body) & (body > 0), -1, 0))
    out["envolvente"] = np.where(bull & bear1 & (c >= o1) & (o <= c1) & (body > b1), 1,
                                 np.where(bear & bull1 & (c <= o1) & (o >= c1) & (body > b1), -1, 0))
    out["harami"] = np.where(bull & bear1 & (c < o1) & (o > c1), 1, np.where(bear & bull1 & (c > o1) & (o < c1), -1, 0))
    big2 = b2 >= 0.6 * r2
    small1 = b1 <= 0.3 * r1
    out["estrella"] = np.where((c2 < o2) & big2 & small1 & bull & (c > (o2 + c2) / 2), 1,
                               np.where((c2 > o2) & big2 & small1 & bear & (c < (o2 + c2) / 2), -1, 0))
    strong = body >= 0.5 * rng
    s1, s2 = sh(strong.astype(float)) == 1, sh(strong.astype(float), 2) == 1
    out["tres soldados"] = np.where(bull & bull1 & (c2 > o2) & strong & s1 & s2 & (c > c1) & (c1 > c2), 1,
                                    np.where(bear & bear1 & (c2 < o2) & strong & s1 & s2 & (c < c1) & (c1 < c2), -1, 0))
    out["marubozu"] = np.where(ok & bull & (body >= 0.9 * rng), 1, np.where(ok & bear & (body >= 0.9 * rng), -1, 0))
    tol = 0.05 * np.maximum(rng, r1)
    out["pinzas"] = np.where(bear1 & bull & (np.abs(l - l1) <= tol), 1, np.where(bull1 & bear & (np.abs(h - h1) <= tol), -1, 0))
    # extremo del patrón para el stop
    span = {"martillo": 1, "envolvente": 2, "harami": 2, "estrella": 3, "tres soldados": 3, "marubozu": 1, "pinzas": 2}
    lo_ext = {p: pd.Series(l).rolling(k).min().to_numpy() for p, k in span.items()}
    hi_ext = {p: pd.Series(h).rolling(k).max().to_numpy() for p, k in span.items()}
    return out, lo_ext, hi_ext


@njit(cache=True)
def sim(o5, h5, l5, c5, k5, sides, stops, end5, rr, cost, usd):
    n = len(k5)
    out = np.full(n, np.nan)
    busy = -1
    for i in range(n):
        k = k5[i]
        if k <= busy or k >= end5[i]:
            continue
        s = sides[i]
        e = o5[k]
        sl = stops[i]
        risk = s * (e - sl)
        if risk <= 0:
            continue
        tg = e + s * rr * risk if rr > 0 else np.nan
        px = c5[end5[i]]
        q_end = end5[i]
        for q in range(k, end5[i] + 1):
            if (s == 1 and l5[q] <= sl) or (s == -1 and h5[q] >= sl):
                px = min(sl, o5[q]) if s == 1 else max(sl, o5[q])
                q_end = q
                break
            if rr > 0 and ((s == 1 and h5[q] >= tg) or (s == -1 and l5[q] <= tg)):
                px = tg
                q_end = q
                break
        busy = q_end
        out[i] = (s * (px - e) - cost) * usd
    return out


def summarize(rows, sym, tf, pat, size, mode, obj, years, u):
    m = np.isfinite(u)
    u, years = u[m], years[m]
    if len(u) < 100:
        return
    d, v = u[years < 2023], u[years >= 2023]
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = np.cumsum(u)
    rows.append(dict(activo=sym, tf=tf, patron=pat, tamaño=size, direccion=mode, obj=obj, ops_año=round(len(u) / 8.75),
                     acierto=round((u > 0).mean(), 2), dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75),
                     pf_val=pf(v), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                     años=f"{sum(u[years == y].sum() > 0 for y in range(2018, 2027))}/9"))


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        d5 = load_5m(sym)
        t5 = d5.index
        o5, h5, l5, c5 = (d5[k].to_numpy() for k in ("open", "high", "low", "close"))
        m5 = (t5.hour * 60 + t5.minute).to_numpy()
        # índice de la última vela de 5 min antes de las 16:00 NY de ese día natural
        day5 = np.array(t5.normalize().asi8)
        last_rth = pd.Series(np.where(m5 < 960, np.arange(len(t5)), -1)).groupby(day5).max()
        for tf, rule, off in (("5m", None, None), ("15m", "15min", None), ("1h", "60min", None), ("4h", "240min", "2h")):
            b = d5 if rule is None else d5.resample(rule, offset=off).agg(
                {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            P, LO, HI = patterns(b)
            pc = b.close.shift()
            tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
            atr = tr.rolling(14).mean().to_numpy()
            tf_min = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}[tf]
            close_t = b.index + pd.Timedelta(minutes=tf_min)
            cm = (close_t.hour * 60 + close_t.minute).to_numpy()
            k5_all = np.searchsorted(t5.asi8, close_t.asi8)
            win = (cm >= 180) & (cm <= 900) & (k5_all < len(t5))
            k5c = np.minimum(k5_all, len(t5) - 1)
            end_all = last_rth.reindex(day5[k5c]).to_numpy()
            big = (b.high - b.low).to_numpy() >= atr
            yrs_all = b.index.year.to_numpy()
            for pat in PATS:
                for size, mode in itertools.product(("todas", "grandes"), ("clásica", "contraria")):
                    sel = win & (P[pat] != 0) & (end_all > k5c) & ((size == "todas") | big)
                    idx = np.flatnonzero(sel)
                    sides = P[pat][idx].astype(np.int64) * (1 if mode == "clásica" else -1)
                    stops = np.where(sides == 1, LO[pat][idx], HI[pat][idx])
                    stops = np.where(sides == 1, stops - (0.25 if sym == "NQ" else 0.1), stops + (0.25 if sym == "NQ" else 0.1))
                    if mode == "contraria":       # el stop del control va al otro lado, a la misma distancia del patrón
                        e0 = o5[k5c[idx]]
                        stops = e0 + (e0 - np.where(sides == -1, LO[pat][idx], HI[pat][idx]))
                    for obj, rr in (("1R", 1.0), ("2R", 2.0), ("cierre", 0.0)):
                        u = sim(o5, h5, l5, c5, k5c[idx].astype(np.int64), sides, stops.astype(float),
                                end_all[idx].astype(np.int64), rr, cost, usd)
                        summarize(rows, sym, tf, pat, size, mode, obj, yrs_all[idx], u)
        # diario: patrón de la vela Globex de ayer → operación 9:30-16:00 de hoy
        gd = (t5 + pd.Timedelta(hours=6)).normalize()
        D = d5.groupby(gd).agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        rth = d5[(m5 >= 570) & (m5 < 960)]
        R = rth.groupby(rth.index.normalize()).agg({"open": "first", "close": "last"})
        R.index = R.index.tz_localize(None)
        D.index = D.index.tz_localize(None)
        P, _, _ = patterns(D)
        pc = D.close.shift()
        tr = np.maximum(D.high - D.low, np.maximum((D.high - pc).abs(), (D.low - pc).abs()))
        big = ((D.high - D.low) >= tr.rolling(14).mean()).to_numpy()
        nxt = D.index[1:]
        for pat in PATS:
            for size, mode in itertools.product(("todas", "grandes"), ("clásica", "contraria")):
                us, ys = [], []
                for i in range(len(D) - 1):
                    s = P[pat][i]
                    if s == 0 or (size == "grandes" and not big[i]) or nxt[i] not in R.index:
                        continue
                    s = s if mode == "clásica" else -s
                    r = R.loc[nxt[i]]
                    us.append((s * (r.close - r.open) - cost) * usd)
                    ys.append(nxt[i].year)
                summarize(rows, sym, "diario", pat, size, mode, "9:30→16:00", np.array(ys), np.array(us))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/patrones_velas_clasicos.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal variantes: {len(R)} · ganan en ambos periodos: {both(R)}")
    for keys in (["activo", "direccion"], ["activo", "tf"], ["activo", "patron"]):
        print(R.groupby(keys).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g), "acierto medio": round(g.acierto.mean(), 2),
                                                          "med dev": int(g.dev.median()), "med val": int(g.val.median())}),
                                    include_groups=False).to_string())
    C = R[(R.dev > 0) & (R.val > 0) & (R.años.str[0].astype(int) >= 7)]
    print(f"\n══ Ganan en ambos periodos y ≥ 7/9 años: {len(C)} ══")
    print(C.sort_values("acierto", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
