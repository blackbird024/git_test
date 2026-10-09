"""AMD intradía en 5 min: rango (acumulación) → barrida del rango (manipulación) → entrada hacia el otro lado (distribución).
NQ / MNQ y oro / MGC, 2018 - oct 2026.

Acumulación: las últimas N velas de 5 min (N = 6 → 30 min · N = 12 → 1 h) forman un rango de alto ≤ k × ATR(14) de 5 min
             (k = 2 · 3 · 4). El rango se fija al detectarlo.
Manipulación: en las 6 velas siguientes, una vela supera el máximo (o mínimo) del rango con la mecha y CIERRA dentro del rango.
Distribución (entrada): en la apertura de la vela siguiente, en dirección contraria a la barrida.
  Stop: 1 tick más allá del extremo de la barrida. Objetivo: el otro lado del rango · 2R · 3R. Cierre forzoso 16:00 NY.
Control: «ruptura» = la vela CIERRA fuera del rango → entrar a favor (lo contrario de la manipulación), stop en el otro lado.
Filtro opcional: sesgo RSI 14 de 1 h en contra (como el rango de ayer) — solo compras si RSI < 50, ventas si > 50.
Sesiones: Londres (3:00-8:00 NY = 9:00-14:00 Italia) · NY (9:30-15:00 NY = 15:30-21:00 Italia). Máx. 2 operaciones por sesión.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python amd_5m_rango.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

import mezcla_filtros as M
from crt_backtest import load_5m


@njit(cache=False)
def run(o, h, l, c, atr, hm, day, eod, rsi, N, k, mode, tgt_mode, use_bias, ses_a, ses_b, tick, cost):
    n = len(c)
    out_i = np.empty(n, np.int64)
    out_u = np.empty(n, np.float64)
    m = 0
    i = N
    cnt_day = -1
    cnt = 0
    while i < n - 2:
        if hm[i] < ses_a or hm[i] > ses_b or not np.isfinite(atr[i]):
            i += 1
            continue
        if day[i] != cnt_day:
            cnt_day = day[i]
            cnt = 0
        if cnt >= 2:
            i += 1
            continue
        H = h[i - N:i].max()
        L = l[i - N:i].min()
        if H - L > k * atr[i - 1] or H - L <= 0:
            i += 1
            continue
        found = False
        for j in range(i, min(i + 6, n - 1)):
            if hm[j] > ses_b or day[j] != day[i]:
                break
            s = 0
            sl = 0.0
            tg = 0.0
            if mode == 0:                                   # manipulación: mecha fuera y cierre dentro
                if h[j] > H and L < c[j] < H:
                    s, sl = -1, h[j] + tick
                elif l[j] < L and L < c[j] < H:
                    s, sl = 1, l[j] - tick
            else:                                           # control: ruptura con cierre fuera
                if c[j] > H:
                    s, sl = 1, L - tick
                elif c[j] < L:
                    s, sl = -1, H + tick
            if s == 0:
                if c[j] > H or c[j] < L:
                    break                                   # el rango se rompió sin manipulación
                continue
            if use_bias == 1 and np.isfinite(rsi[j]) and -rsi[j] != s:
                found = True
                i = j + 1
                break
            k0 = j + 1
            if eod[k0] < k0:
                found = True
                i = j + 1
                break
            e = o[k0]
            risk = s * (e - sl)
            if risk <= 0:
                found = True
                i = j + 1
                break
            if tgt_mode == 0:
                tg = L if s == -1 else H
                if s * (tg - e) <= 0:
                    found = True
                    i = j + 1
                    break
            else:
                tg = e + s * tgt_mode * risk
            px = c[eod[k0]]
            qe = eod[k0]
            for q in range(k0, eod[k0] + 1):
                if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                    px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                    qe = q
                    break
                if (s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg):
                    px = tg
                    qe = q
                    break
            out_i[m] = k0
            out_u[m] = s * (px - e) - cost
            m += 1
            cnt += 1
            i = qe + 1
            found = True
            break
        if not found:
            i += 1
    return out_i[:m], out_u[:m]


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd, tick in (("NQ", 1.0, 2.0, 0.25), ("GC", 0.3, 10.0, 0.1)):
        df = load_5m(sym)
        t = df.index
        hm = (t.hour * 60 + t.minute).to_numpy().astype(np.int64)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        pc = np.r_[c[0], c[:-1]]
        tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        day = np.array(t.normalize().asi8 // 86_400_000_000_000).astype(np.int64)
        eod = pd.Series(np.where(hm < 960, np.arange(len(t)), -1)).groupby(day).max().reindex(day).to_numpy().astype(np.int64)
        rsi = M.context(df)["RSI 1h"].astype(float)
        yrs = t.year.to_numpy()
        for (ses, a, b), N, k, mode, tg, bias in itertools.product((("Londres", 180, 480), ("NY", 570, 900)), (6, 12), (2.0, 3.0, 4.0),
                                                                     (0, 1), (0.0, 2.0, 3.0), (0, 1)):
            I, U = run(o, h, l, c, atr, hm, day, eod, rsi, N, k, mode, tg, bias, a, b, tick, cost)
            if len(U) < 80:
                continue
            u = U * usd
            y = yrs[I]
            dv, vv = u[y < 2023], u[y >= 2023]
            pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
            eq = np.cumsum(u)
            rows.append(dict(activo=sym, sesion=ses, rango=f"{N * 5} min ≤ {k:g} ATR", tipo="manipulación" if mode == 0 else "ruptura (control)",
                             obj={0.0: "otro lado", 2.0: "2R", 3.0: "3R"}[tg], sesgo="RSI en contra" if bias else "—",
                             ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2), dev=round(dv.sum() / 5), pf_dev=pf(dv),
                             val=round(vv.sum() / 3.75), pf_val=pf(vv), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                             años=f"{sum(u[y == yy].sum() > 0 for yy in range(2018, 2027))}/9"))
        print(sym, "listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/amd_5m_rango.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(R.groupby(["activo", "sesion", "tipo", "sesgo"]).apply(lambda g: pd.Series({"n": len(g), "% ganan ambos": both(g),
          "acierto": round(g.acierto.mean(), 2), "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    C = R[(R.tipo == "manipulación") & (R.dev > 0) & (R.val > 0)]
    print(f"\n══ Manipulación que gana en ambos periodos: {len(C)} ══")
    print(C.sort_values("val", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
