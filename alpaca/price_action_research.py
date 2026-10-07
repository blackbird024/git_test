"""Price action puro en niveles: pin bar, envolvente, inside bar, falsa ruptura y ruptura-retesteo.
NQ / MNQ y oro (GC / MGC), velas de 5 y 15 min, sesiones de Londres y Nueva York.

Niveles del día: máximo/mínimo de ayer (sesión Globex), de Asia (20:00-00:00 NY) y, para NY, de Londres
(02:00-05:00 NY). Cada nivel se usa una vez por día. Patrones (para un nivel por ENCIMA del precio → corto;
espejo para un nivel por debajo → largo):
  pin        la vela toca el nivel, cierra por debajo y su mecha superior es ≥ 60 % del rango
  envolvente la vela (o la anterior) toca el nivel, cierra por debajo, es bajista y envuelve el cuerpo alcista anterior
  inside     vela madre toca el nivel y cierra por debajo; la siguiente queda dentro → venta STOP en el mínimo de
             la madre (válida 3 velas), stop en su máximo
  falsa      la vela supera el nivel y cierra por debajo (cualquier forma de vela)
  retesteo   una vela CIERRA por encima del nivel (ruptura); después el precio vuelve a tocarlo y una vela cierra
             por encima otra vez → LARGO a favor de la ruptura (continuación)
Entrada: a mercado en la apertura siguiente, o con orden STOP en el extremo de la vela de señal (válida 2 velas).
Stop: el otro extremo de la vela de señal. Objetivo: 1R, 2R, 3R o cierre de la sesión.
Filtro: ninguno / solo a favor de la tendencia de 1 h (EMA 20/50) / solo en contra.
Sesiones (hora NY): Londres entradas 2:00-5:00, cierre 11:30 · NY entradas 9:30-15:00, cierre 16:00.
Coste: NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python price_action_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

import ict_research as I
from crt_backtest import load_5m
from ema_cross_research import align, tf_frame

ASSETS = {"NQ": (1.0, 2.0), "GC": (0.3, 10.0)}
SESS = {"Londres": (120, 300, 690, ("pdH", "pdL", "asiaH", "asiaL")),
        "NY": (570, 900, None, ("pdH", "pdL", "asiaH", "asiaL", "ldnH", "ldnL"))}
PATS = ["pin", "envolvente", "inside", "falsa", "retesteo"]


@njit(cache=True)
def sim(o, h, l, c, trend, s0, s1, xe, lv, pat, emode, rr, filt, cost, maxn):
    nd, nl = lv.shape
    pnl = np.empty(nd * maxn)
    rmul = np.empty(nd * maxn)
    day = np.empty(nd * maxn, np.int64)
    nt = 0
    for d in range(nd):
        a, b, x1 = s0[d], s1[d], xe[d]
        if a < 1 or b <= a or x1 <= b:
            continue
        used = np.zeros(nl, np.bool_)
        broke = np.zeros(nl, np.int64)     # para retesteo: +1 roto hacia arriba, -1 hacia abajo
        ntr = 0
        pos, e, sl, tg = 0, 0.0, 0.0, 0.0
        pend, pe, ps, pexp = 0, 0.0, 0.0, 0
        for i in range(a, x1 + 1):
            if pos != 0:
                out = np.nan
                if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                    out = min(sl, o[i]) if pos == 1 else max(sl, o[i])
                elif rr > 0 and ((pos == 1 and h[i] >= tg) or (pos == -1 and l[i] <= tg)):
                    out = tg
                elif i == x1:
                    out = c[i]
                if out == out:
                    pnl[nt] = pos * (out - e) - cost
                    rmul[nt] = pos * (out - e) / abs(e - sl)
                    day[nt] = d
                    nt += 1
                    pos = 0
                continue
            if i > b or ntr >= maxn:
                continue
            if pend != 0:
                if i > pexp:
                    pend = 0
                elif (pend == 1 and h[i] >= pe) or (pend == -1 and l[i] <= pe):
                    fill = max(pe, o[i]) if pend == 1 else min(pe, o[i])
                    if (pend == 1 and fill > ps) or (pend == -1 and fill < ps):
                        pos, e, sl = pend, fill, ps
                        tg = e + pos * rr * abs(e - sl)
                        ntr += 1
                        pend = 0
                        if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                            pnl[nt] = -abs(e - sl) - cost
                            rmul[nt] = -1.0
                            day[nt] = d
                            nt += 1
                            pos = 0
                        continue
                    pend = 0
                if pend != 0:
                    continue
            for q in range(nl):
                L = lv[d, q]
                if L != L or used[q]:
                    continue
                s = 0
                sig_ext, sig_far = 0.0, 0.0
                rng = h[i] - l[i]
                if pat == 4:
                    # ruptura: cierre al otro lado viniendo del lado contrario
                    if broke[q] == 0:
                        if c[i - 1] < L and c[i] > L:
                            broke[q] = 1
                        elif c[i - 1] > L and c[i] < L:
                            broke[q] = -1
                        continue
                    if broke[q] == 1 and l[i] <= L and c[i] > L:
                        s, sig_ext, sig_far = 1, h[i], l[i]
                    elif broke[q] == -1 and h[i] >= L and c[i] < L:
                        s, sig_ext, sig_far = -1, l[i], h[i]
                    elif (broke[q] == 1 and c[i] < L) or (broke[q] == -1 and c[i] > L):
                        broke[q] = 0
                    if s == 0:
                        continue
                else:
                    above = o[i] < L or c[i - 1] < L        # el nivel está por encima: resistencia
                    below = o[i] > L or c[i - 1] > L
                    if pat == 0 and rng > 0:
                        if above and h[i] >= L and c[i] < L and (h[i] - max(o[i], c[i])) >= 0.6 * rng:
                            s = -1
                        elif below and l[i] <= L and c[i] > L and (min(o[i], c[i]) - l[i]) >= 0.6 * rng:
                            s = 1
                    elif pat == 1:
                        if max(h[i], h[i - 1]) >= L and c[i] < L and c[i] < o[i] and c[i - 1] > o[i - 1] \
                                and c[i] <= o[i - 1] and o[i] >= c[i - 1] and c[i - 1] < L + (h[i] - l[i]):
                            s = -1
                        elif min(l[i], l[i - 1]) <= L and c[i] > L and c[i] > o[i] and c[i - 1] < o[i - 1] \
                                and c[i] >= o[i - 1] and o[i] <= c[i - 1] and c[i - 1] > L - (h[i] - l[i]):
                            s = 1
                    elif pat == 2:
                        m = i - 1
                        if h[m] >= L and c[m] < L and o[m] < L and h[i] <= h[m] and l[i] >= l[m]:
                            s = -1
                        elif l[m] <= L and c[m] > L and o[m] > L and h[i] <= h[m] and l[i] >= l[m]:
                            s = 1
                    elif pat == 3:
                        if above and h[i] > L and c[i] < L:
                            s = -1
                        elif below and l[i] < L and c[i] > L:
                            s = 1
                    if s == 0:
                        continue
                    if pat == 2:
                        sig_ext = l[i - 1] if s == -1 else h[i - 1]
                        sig_far = h[i - 1] if s == -1 else l[i - 1]
                    else:
                        sig_ext = l[i] if s == -1 else h[i]
                        sig_far = h[i] if s == -1 else l[i]
                used[q] = True
                if filt == 1 and trend[i] != s:
                    continue
                if filt == 2 and trend[i] != -s:
                    continue
                if emode == 0 and pat != 2:
                    pos, e, sl = s, o[i + 1], sig_far
                    if (s == 1 and e <= sl) or (s == -1 and e >= sl):
                        pos = 0
                        continue
                    tg = e + s * rr * abs(e - sl)
                    ntr += 1
                else:
                    pend, pe, ps, pexp = s, sig_ext, sig_far, i + (3 if pat == 2 else 2)
                break
    return pnl[:nt], rmul[:nt], day[:nt]


def prep(sym, res):
    df = load_5m(sym)
    if res != 5:
        df = df.resample(f"{res}min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    days = I.day_table(df, res)
    b = tf_frame(load_5m(sym), 60)
    b["st"] = np.sign(b.close.ewm(span=20, adjust=False).mean() - b.close.ewm(span=50, adjust=False).mean())
    trend = np.nan_to_num(align(df, b, ["st"])["st"])
    return df, days, trend


def main():
    pd.set_option("display.width", 260)
    rows = []
    for sym, res in itertools.product(ASSETS, (5, 15)):
        cost, usd = ASSETS[sym]
        df, days, trend = prep(sym, res)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        years = np.array([x["d"].year for x in days])
        for sn, (w0, w1, xm, keys) in SESS.items():
            s0 = np.array([I.at(x, w0) for x in days])
            s1 = np.array([I.at(x, w1) for x in days])
            xe = np.array([x["rth1"] if xm is None else I.at(x, xm) for x in days])
            lv = np.array([[x[k] for k in keys] for x in days], dtype=float)
            for p, em, rr, fl in itertools.product(range(5), (0, 1), (1.0, 2.0, 3.0, 0.0), (0, 1, 2)):
                if p == 2 and em == 0:
                    continue
                pnl, rm, dd = sim(o, h, l, c, trend, s0, s1, xe, lv, p, em, rr, fl, cost, 2)
                if len(pnl) < 40:
                    continue
                y = years[dd]
                u = pnl * usd
                r = dict(activo=sym, tf=f"{res}m", sesion=sn, patron=PATS[p], entrada="mercado" if em == 0 else "stop",
                         obj=f"{rr:g}R" if rr else "cierre", filtro=["-", "a favor 1h", "contra 1h"][fl])
                for name, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
                    v, rv = u[sel], rm[sel]
                    g, ls = v[v > 0].sum(), -v[v < 0].sum()
                    eq = np.cumsum(v)
                    r |= {f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs),
                          f"{name}_pf": round(g / ls, 2) if ls else np.inf, f"{name}_R": round(rv.mean(), 2) if len(rv) else 0}
                    if name == "val":
                        r |= dict(val_dd=round((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0,
                                  val_win=round((v > 0).mean(), 2) if len(v) else 0)
                by = pd.Series(u).groupby(y).sum()
                r["años"] = f"{(by > 0).sum()}/{len(by)}"
                rows.append(r)
        print(f"{sym} {res}m listo", flush=True)
    r = pd.DataFrame(rows)
    r.to_pickle(".lab_cache/price_action.pkl")
    both = lambda g: f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}"
    summ = lambda g: pd.Series({"n": len(g), "% gana ambos": both(g), "med dev $": int(g.dev_usd.median()),
                                "med val $": int(g.val_usd.median()), "med R/op val": round(g.val_R.median(), 2)})
    for sym in ASSETS:
        x = r[r.activo == sym]
        print(f"\n══════════ {sym}: {len(x)} variantes · ganan en ambos periodos: {both(x)} ══════════")
        for col in ("patron", "tf", "sesion", "entrada", "obj", "filtro"):
            print(x.groupby(col).apply(summ, include_groups=False).to_string(), "\n")
        print(x.groupby(["sesion", "patron"]).apply(summ, include_groups=False).to_string(), "\n")
        print("Las 12 con el peor periodo más alto:")
        x = x.assign(minimo=x[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(x.head(12).drop(columns=["minimo"]).to_string(index=False))


if __name__ == "__main__":
    main()
