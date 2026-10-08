"""Soportes / resistencias y trendlines: ¿rebota el precio o los rompe? NQ / MNQ y oro / MGC, 2018 - oct 2026.

Niveles (todos objetivos, sin dibujar a mano):
  swing 1h      máximos y mínimos de swing confirmados en velas de 1 h (fractal de 3 velas a cada lado), válidos
                7 días. «doble» = otro swing a menos de 0,1 ATR diario en los 10 días anteriores (nivel tocado 2+ veces).
  redondo       NQ múltiplos de 100 · oro múltiplos de 10 (y «redondo grande»: NQ 500 · oro 50).
  trendline     línea por dos mínimos de swing de 1 h ascendentes (soporte) o dos máximos descendentes (resistencia),
                sin velas de 1 h que la crucen entre los dos puntos; válida 5 días. El evento es el 3.er toque.
Evento: primera vela de 5 min que toca el nivel viniendo del otro lado (la anterior cerró al otro lado), con la
hora de la vela entre 3:00 y 15:00 NY (Londres + NY). Cada nivel se usa una vez.
Operación en el nivel (orden límite para el rebote / stop para la ruptura, precio = el nivel):
  rebote   a favor del soporte/resistencia (compra en soporte, venta en resistencia)
  ruptura  en contra (vende el soporte, compra la resistencia)
Stop s · ATR diario (s = 0,05 · 0,1 · 0,2) más allá; objetivo 1R o 2R; cierre forzoso 16:00 NY. Una operación a la vez.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python soportes_trendlines.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m


@njit(cache=True)
def first_touch(h5, l5, c5, start, end, a, b, t0, t5h):
    """Primera vela k en [start, end) que toca la línea y = a + b·(horas desde t0) viniendo del otro lado.
    Devuelve (k, lado de aproximación: +1 desde arriba / -1 desde abajo) o (-1, 0)."""
    for k in range(max(start, 1), end):
        y = a + b * (t5h[k] - t0)
        if l5[k] <= y <= h5[k]:
            yp = a + b * (t5h[k - 1] - t0)
            if c5[k - 1] > yp:
                return k, 1
            if c5[k - 1] < yp:
                return k, -1
            return -1, 0
    return -1, 0


@njit(cache=True)
def sim(h5, l5, o5, c5, ks, sides, entries, risks, ends, rr, cost, usd):
    n = len(ks)
    out = np.full(n, np.nan)
    busy = -1
    for i in range(n):
        k = ks[i]
        if k <= busy or ends[i] <= k:
            continue
        s, e = sides[i], entries[i]
        sl = e - s * risks[i]
        tg = e + s * rr * risks[i]
        px = c5[ends[i]]
        qe = ends[i]
        for q in range(k + 1, ends[i] + 1):
            if (s == 1 and l5[q] <= sl) or (s == -1 and h5[q] >= sl):
                px = min(sl, o5[q]) if s == 1 else max(sl, o5[q])
                qe = q
                break
            if (s == 1 and h5[q] >= tg) or (s == -1 and l5[q] <= tg):
                px = tg
                qe = q
                break
        busy = qe
        out[i] = (s * (px - e) - cost) * usd
    return out


def pivots(b, p=3):
    h, l = b.high.to_numpy(), b.low.to_numpy()
    H, L = [], []
    for j in range(p, len(h) - p):
        if h[j] == h[j - p:j + p + 1].max():
            H.append((j, h[j]))
        if l[j] == l[j - p:j + p + 1].min():
            L.append((j, l[j]))
    return H, L


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd, rnd, rnd_big, tick in (("NQ", 1.0, 2.0, 100, 500, 0.25), ("GC", 0.3, 10.0, 10, 50, 0.1)):
        d5 = load_5m(sym)
        t5 = d5.index
        o5, h5, l5, c5 = (d5[k].to_numpy() for k in ("open", "high", "low", "close"))
        t5h = (t5.asi8 - t5.asi8[0]) / 3.6e12
        m5 = (t5.hour * 60 + t5.minute).to_numpy()
        gd = (t5 + pd.Timedelta(hours=6)).normalize()
        D = d5.groupby(gd).agg(high=("high", "max"), low=("low", "min"))
        datr = (D.high - D.low).rolling(14).mean().shift(1)
        atr5 = datr.reindex(gd).to_numpy()
        day5 = np.array(t5.normalize().asi8)
        end_of_day = pd.Series(np.where(m5 < 960, np.arange(len(t5)), -1)).groupby(day5).max().reindex(day5).to_numpy()
        inwin = (m5 >= 180) & (m5 <= 900)
        h1 = d5.resample("60min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        h1h = (h1.index.asi8 - t5.asi8[0]) / 3.6e12
        conf_k = lambda j: int(np.searchsorted(t5.asi8, h1.index.asi8[j + 3] + 3_600_000_000_000))
        H, L = pivots(h1)
        ev = []   # (k, side_rebote, nivel, tipo, fuerza)

        def add(kind, strength, a, b, t0, start, end):
            k, appr = first_touch(h5, l5, c5, start, min(end, len(t5)), a, b, t0, t5h)
            if k < 0 or not inwin[k] or not np.isfinite(atr5[k]) or end_of_day[k] <= k:
                return
            lvl = a + b * (t5h[k] - t0)
            ev.append((k, appr, lvl, kind, strength))     # rebote: desde arriba → compra (+1); desde abajo → venta (−1)

        # swings horizontales
        for piv, other in ((H, L), (L, H)):
            allp = sorted(H + L)
            ap_j = np.array([j for j, _ in allp])
            ap_v = np.array([v for _, v in allp])
            for j, v in piv:
                start = conf_k(j) if j + 3 < len(h1) else len(t5)
                if start >= len(t5):
                    continue
                a5 = atr5[min(start, len(t5) - 1)]
                prev = (ap_j < j) & (ap_j >= j - 240) & (np.abs(ap_v - v) <= 0.1 * a5)
                add("swing 1h", "doble" if prev.any() else "simple", v, 0.0, 0.0, start, start + 7 * 288)
        # números redondos: cada día, el primer toque de cada redondo cerca del precio
        for d, idx in pd.Series(np.arange(len(t5))).groupby(day5).indices.items():
            idx = np.asarray(idx)
            w = idx[inwin[idx]]
            if len(w) < 10:
                continue
            lo, hi = l5[w].min(), h5[w].max()
            for lvl in np.arange(np.ceil(lo / rnd) * rnd, hi + 1e-9, rnd):
                add("redondo grande" if abs(lvl / rnd_big - round(lvl / rnd_big)) < 1e-9 else "redondo", "-", float(lvl), 0.0, 0.0, w[0], w[-1] + 1)
        # trendlines
        for piv, rising in ((L, True), (H, False)):
            for (j1, v1), (j2, v2) in zip(piv[:-1], piv[1:]):
                if (rising and v2 <= v1) or (not rising and v2 >= v1) or j2 - j1 < 5 or j2 + 3 >= len(h1):
                    continue
                b = (v2 - v1) / (h1h[j2] - h1h[j1])
                line = v1 + b * (h1h[j1:j2 + 1] - h1h[j1])
                seg_l, seg_h = h1.low.to_numpy()[j1:j2 + 1], h1.high.to_numpy()[j1:j2 + 1]
                if (rising and (seg_l < line - 1e-9).any()) or (not rising and (seg_h > line + 1e-9).any()):
                    continue
                start = conf_k(j2)
                add("trendline", "alcista" if rising else "bajista", v1, b, h1h[j1], start, start + 5 * 288)
        E = pd.DataFrame(ev, columns=["k", "appr", "lvl", "tipo", "fuerza"]).sort_values("k").reset_index(drop=True)
        E["y"] = t5.year.to_numpy()[E.k]
        E["ses"] = np.where(m5[E.k] < 570, "Londres", "NY")
        print(sym, E.groupby(["tipo", "fuerza"]).size().to_dict(), flush=True)
        for (tipo, fuerza, ses), g in E.groupby(["tipo", "fuerza", "ses"]):
            ks = g.k.to_numpy().astype(np.int64)
            ends = end_of_day[ks].astype(np.int64)
            for mode, s_, rr in itertools.product(("rebote", "ruptura"), (0.05, 0.1, 0.2), (1.0, 2.0)):
                sides = g.appr.to_numpy().astype(np.int64) * (1 if mode == "rebote" else -1)
                u = sim(h5, l5, o5, c5, ks, sides, g.lvl.to_numpy(), s_ * atr5[ks], ends, rr, cost, usd)
                m = np.isfinite(u)
                u, yrs = u[m], g.y.to_numpy()[m]
                if len(u) < 80:
                    continue
                dv, vv = u[yrs < 2023], u[yrs >= 2023]
                pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
                eq = np.cumsum(u)
                rows.append(dict(activo=sym, tipo=tipo, fuerza=fuerza, sesion=ses, modo=mode, stop_atr=s_, obj=f"{rr:g}R",
                                 ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2), dev=round(dv.sum() / 5), pf_dev=pf(dv),
                                 val=round(vv.sum() / 3.75), pf_val=pf(vv), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                                 años=f"{sum(u[yrs == y].sum() > 0 for y in range(2018, 2027))}/9"))
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/soportes_trendlines.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal variantes: {len(R)} · ganan en ambos periodos: {both(R)}")
    print(R.groupby(["activo", "tipo", "modo"]).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g), "acierto medio": round(g.acierto.mean(), 2),
          "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    C = R[(R.dev > 0) & (R.val > 0) & (R.años.str[0].astype(int) >= 7)]
    print(f"\n══ Ganan en ambos periodos y ≥ 7/9 años: {len(C)} ══")
    print(C.sort_values("val", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
