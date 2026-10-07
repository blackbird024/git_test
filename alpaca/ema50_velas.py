"""Patrones de velas en la EMA 50 (retroceso a la media en tendencia), NQ / MNQ y oro / MGC.

Para largos (cortos al revés), en la vela de señal la EMA 50 actúa de soporte:
  pin        el mínimo toca la EMA 50, cierra por encima y la mecha inferior es ≥ 60 % del rango
  envolvente la vela (o la anterior) toca la EMA 50, cierra por encima, es alcista y envuelve el cuerpo bajista anterior
  rechazo    el mínimo toca la EMA 50 y la vela cierra alcista por encima (cualquier forma)
  inside     vela madre toca la EMA 50 y cierra encima; la siguiente queda dentro → compra STOP en el máximo de la madre
Filtro de tendencia: ninguno · EMA 50 subiendo (vs 12 velas antes) · EMA 50 sobre EMA 200 · ambos.
Entrada: a mercado (apertura siguiente) o con orden STOP en el máximo de la vela de señal (válida 2 velas).
Stop: el mínimo de la vela de señal (o de la madre). Objetivo: 1R, 2R, 3R o cierre de la sesión.
Sesiones (hora NY): NY entradas 9:30-15:30 y cierre 16:00 · Londres entradas 3:00-8:00 y cierre 11:30.
Máximo 2 operaciones al día. Coste: NQ 1 punto (2 $/punto) · oro 0,3 puntos (10 $/punto). 2018 - oct 2026.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python ema50_velas.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

PATS = ["pin", "envolvente", "rechazo", "inside"]
FILTS = ["-", "EMA50 sube", "EMA50 > EMA200", "ambos"]


@njit(cache=True)
def sim(o, h, l, c, e50, tr, day, can, last, pat, filt, emode, rr, maxn, cost):
    n = len(c)
    pnl = np.empty(n)
    dd = np.empty(n, np.int64)
    nt = 0
    pos, e, sl, tg, cnt = 0, 0.0, 0.0, 0.0, 0
    pend, pe, ps, pexp = 0, 0.0, 0.0, 0
    for i in range(2, n - 1):
        if day[i] < 0:
            continue
        if day[i] != day[i - 1]:
            cnt = 0
            pend = 0
        if pos != 0:
            out = np.nan
            if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                out = min(sl, o[i]) if pos == 1 else max(sl, o[i])
            elif rr > 0 and ((pos == 1 and h[i] >= tg) or (pos == -1 and l[i] <= tg)):
                out = tg
            elif last[i]:
                out = c[i]
            if out == out:
                pnl[nt] = pos * (out - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
            continue
        if last[i]:
            pend = 0
            continue
        if pend != 0:
            if i > pexp:
                pend = 0
            elif (pend == 1 and h[i] >= pe) or (pend == -1 and l[i] <= pe):
                fill = max(pe, o[i]) if pend == 1 else min(pe, o[i])
                if (pend == 1 and fill > ps) or (pend == -1 and fill < ps):
                    pos, e, sl = pend, fill, ps
                    tg = e + pos * rr * abs(e - sl)
                    cnt += 1
                    if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                        pnl[nt] = -abs(e - sl) - cost
                        dd[nt] = day[i]
                        nt += 1
                        pos = 0
                pend = 0
                continue
            else:
                continue
        if not can[i] or cnt >= maxn:
            continue
        L = e50[i]
        rng = h[i] - l[i]
        s = 0
        if pat == 0 and rng > 0:
            if l[i] <= L and c[i] > L and (min(o[i], c[i]) - l[i]) >= 0.6 * rng:
                s = 1
            elif h[i] >= L and c[i] < L and (h[i] - max(o[i], c[i])) >= 0.6 * rng:
                s = -1
        elif pat == 1:
            if min(l[i], l[i - 1]) <= L and c[i] > L and c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
                s = 1
            elif max(h[i], h[i - 1]) >= L and c[i] < L and c[i] < o[i] and c[i - 1] > o[i - 1] and c[i] <= o[i - 1] and o[i] >= c[i - 1]:
                s = -1
        elif pat == 2:
            if l[i] <= L and c[i] > L and c[i] > o[i]:
                s = 1
            elif h[i] >= L and c[i] < L and c[i] < o[i]:
                s = -1
        else:
            m = i - 1
            if l[m] <= e50[m] and c[m] > e50[m] and h[i] <= h[m] and l[i] >= l[m]:
                s = 1
            elif h[m] >= e50[m] and c[m] < e50[m] and h[i] <= h[m] and l[i] >= l[m]:
                s = -1
        if s == 0:
            continue
        if filt > 0 and tr[i, filt - 1] != s:
            continue
        if pat == 3:
            pend, pe, ps, pexp = s, (h[i - 1] if s == 1 else l[i - 1]), (l[i - 1] if s == 1 else h[i - 1]), i + 3
        elif emode == 1:
            pend, pe, ps, pexp = s, (h[i] if s == 1 else l[i]), (l[i] if s == 1 else h[i]), i + 2
        else:
            pos, e = s, o[i + 1]
            sl = l[i] if s == 1 else h[i]
            if (s == 1 and e <= sl) or (s == -1 and e >= sl):
                pos = 0
                continue
            tg = e + s * rr * abs(e - sl)
            cnt += 1
    return pnl[:nt], dd[:nt]


def main():
    pd.set_option("display.width", 250)
    to_year = lambda x: x.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        d5 = load_5m(sym)
        for tf in (5, 15):
            b = d5 if tf == 5 else d5.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            t = b.index
            hm = (t.hour * 60 + t.minute).to_numpy()
            gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
            o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
            e50 = b.close.ewm(span=50, adjust=False).mean().to_numpy()
            e200 = b.close.ewm(span=200, adjust=False).mean().to_numpy()
            k12 = 60 // tf
            up = np.where(e50 > np.r_[np.full(k12, np.nan), e50[:-k12]], 1, -1)
            ab = np.where(e50 > e200, 1, -1)
            tr = np.c_[up, ab, np.where(up == ab, up, 0)].astype(np.int64)
            sess = {"NY": ((hm >= 570) & (hm < 960), (hm >= 570) & (hm <= 930 - tf), hm == 960 - tf),
                    "Londres": ((hm >= 180) & (hm < 690), (hm >= 180) & (hm <= 480 - tf), hm == 690 - tf)}
            for sn, (win, can, last) in sess.items():
                day = np.where(win, gday, -1)
                for p, fl, em, rr in itertools.product(range(4), range(4), (0, 1), (1.0, 2.0, 3.0, 0.0)):
                    if p == 3 and em == 0:
                        continue
                    pnl, dd = sim(o, h, l, c, e50, tr, day, can, last, p, fl, em, rr, 2, cost)
                    if len(pnl) < 40:
                        continue
                    y = to_year(dd)
                    u = pnl * usd
                    r = dict(activo=sym, tf=f"{tf}m", sesion=sn, patron=PATS[p], filtro=FILTS[fl],
                             entrada="mercado" if em == 0 else "stop", obj=f"{rr:g}R" if rr else "cierre")
                    for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
                        v = u[sel]
                        g, ls = v[v > 0].sum(), -v[v < 0].sum()
                        r |= {f"{nm_}_ops": round(len(v) / yrs), f"{nm_}_usd": round(v.sum() / yrs), f"{nm_}_pf": round(g / ls, 2) if ls else np.inf}
                    eq = np.cumsum(u)
                    r["dd"] = round((np.maximum.accumulate(eq) - eq).max())
                    r["acierto"] = round((u > 0).mean(), 2)
                    r["años"] = f"{(pd.Series(u).groupby(y).sum() > 0).sum()}/{len(set(y))}"
                    rows.append(r)
            print(f"{sym} {tf}m listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/ema50_velas.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    summ = lambda x: pd.Series({"n": len(x), "% ambos": both(x), "med dev $": int(x.dev_usd.median()), "med val $": int(x.val_usd.median()),
                                "med PF val": x.val_pf.median(), "acierto": x.acierto.median()})
    for sym in ("NQ", "GC"):
        X = R[R.activo == sym]
        print(f"\n══════ {sym}: {len(X)} variantes · ganan en ambos periodos: {both(X)} ══════")
        print(X.groupby(["sesion", "patron"]).apply(summ, include_groups=False).to_string(), "\n")
        print(X.groupby(["tf", "filtro"]).apply(summ, include_groups=False).to_string(), "\n")
        print(X.groupby("obj").apply(summ, include_groups=False).to_string(), "\n")
        S = X.assign(mn=X[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
        print(S.head(12).drop(columns="mn").to_string(index=False))


if __name__ == "__main__":
    main()
