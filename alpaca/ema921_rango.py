"""EMA 9/21 en 5 min en NQ descartando los cruces que ocurren con el precio EN RANGO.

Formas de detectar el rango (todas calculadas con velas de 5 min y conocidas al cierre de la vela de señal):
  ADX        ADX(14) por debajo del umbral → rango
  separacion |EMA 9 − EMA 21| menor que k · ATR(14) → medias pegadas → rango
  ER         eficiencia de Kaufman (20 velas): |cierre − cierre de hace 20| / suma de movimientos < umbral → rango
  CHOP       índice de choppiness (14) por encima del umbral → rango
  cruces     hubo otro cruce de las medias en las últimas N velas → serrucho → rango
  caja       el rango de las últimas 24 velas (2 h) es menor que k · ATR diario → compresión → rango
Se aplica sobre las versiones de ema921_5m.py (cruce y retroceso, con y sin VWAP de Globex, tres salidas).
Datos: NQ 2018 - oct 2026; se ELIGE con 2018-2022 y se JUZGA con 2023-2026. Coste 1 punto; 1 MNQ.

Uso:
    python ema921_rango.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from ema_cross_research import align, tf_frame

COST, USD = 1.0, 2.0


@njit(cache=True)
def sim(o, h, l, c, e9, e21, atr, rok, fvw, day, can, last, etype, filt, stopm, rr, xcross, maxn, cost):
    n = len(o)
    pnl = np.empty(n)
    dd = np.empty(n, np.int64)
    nt = 0
    pos, e, sl, tg, cnt = 0, 0.0, 0.0, 0.0, 0
    for i in range(2, n - 1):
        if day[i] < 0:
            continue
        if day[i] != day[i - 1]:
            cnt = 0
        st = 1 if e9[i] > e21[i] else -1
        stp = 1 if e9[i - 1] > e21[i - 1] else -1
        if pos != 0:
            out = np.nan
            if stopm > 0 and ((pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl)):
                out = min(sl, o[i]) if pos == 1 else max(sl, o[i])
            elif rr > 0 and ((pos == 1 and h[i] >= tg) or (pos == -1 and l[i] <= tg)):
                out = tg
            elif last[i]:
                out = c[i]
            elif xcross and st != pos:
                out = o[i + 1]
            if out == out:
                pnl[nt] = pos * (out - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
                if last[i]:
                    continue
        if pos != 0 or not can[i] or last[i] or cnt >= maxn or not rok[i]:
            continue
        sig = 0
        if etype == 0:
            if st != stp:
                sig = st
        else:
            if st == 1 and l[i] <= e9[i] and c[i] > e21[i] and c[i] > o[i]:
                sig = 1
            elif st == -1 and h[i] >= e9[i] and c[i] < e21[i] and c[i] < o[i]:
                sig = -1
        if sig == 0:
            continue
        if filt == 1 and fvw[i] != sig:
            continue
        pos = sig
        e = o[i + 1]
        risk = stopm * atr[i] if stopm > 0 else 0.0
        sl = e - pos * risk
        tg = e + pos * rr * risk
        cnt += 1
    return pnl[:nt], dd[:nt]


def main():
    pd.set_option("display.width", 250)
    from vwap_globex_8y import load
    d = load()[["open", "high", "low", "close", "volume"]].sort_index()
    d.index = d.index.tz_convert("America/New_York")
    b = d.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    t = b.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
    cs = b.close
    e9 = cs.ewm(span=9, adjust=False).mean().to_numpy()
    e21 = cs.ewm(span=21, adjust=False).mean().to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = pd.Series(np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc))))
    atr = tr.rolling(14).mean().bfill().to_numpy()
    # VWAP de Globex
    typ = (h + l + c) / 3
    v = b.volume.to_numpy().astype(float)
    g = pd.Series(gday)
    vw = (pd.Series(typ * v).groupby(g).cumsum() / pd.Series(v).groupby(g).cumsum().replace(0, np.nan)).to_numpy()
    fvw = np.where(c > vw, 1, -1)
    # ── detectores de rango
    up = pd.Series(h).diff()
    dn = -pd.Series(l).diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    rma = lambda x: pd.Series(x).ewm(alpha=1 / 14, adjust=False).mean()
    atrw = rma(tr)
    pdi, ndi = 100 * rma(pdm) / atrw, 100 * rma(ndm) / atrw
    adx = rma(100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)).fillna(0).to_numpy()
    sep = np.abs(e9 - e21) / atr
    er = (cs.diff(20).abs() / cs.diff().abs().rolling(20).sum()).fillna(0).to_numpy()
    chop = (100 * np.log10(tr.rolling(14).sum() / (pd.Series(h).rolling(14).max() - pd.Series(l).rolling(14).min())) / np.log10(14)).fillna(100).to_numpy()
    st = np.sign(e9 - e21)
    xing = pd.Series((st != np.r_[st[0], st[:-1]]).astype(int))
    prev_x = lambda n: (xing.rolling(n).sum() - xing).fillna(0).to_numpy()     # cruces en las n velas anteriores
    # ATR diario (rango de la sesión regular, 14 sesiones) para la «caja»
    rth = (hm >= 570) & (hm < 960)
    dr = pd.DataFrame({"h": h[rth], "l": l[rth], "g": gday[rth]}).groupby("g").agg(h=("h", "max"), l=("l", "min"))
    datr = (dr.h - dr.l).rolling(14).mean().shift(1)
    datr_bar = pd.Series(gday).map(datr).to_numpy()
    box24 = (pd.Series(h).rolling(24).max() - pd.Series(l).rolling(24).min()).to_numpy()
    filters = {
        "ninguno": np.ones(len(c), bool),
        "ADX > 20": adx > 20, "ADX > 25": adx > 25, "ADX > 30": adx > 30,
        "separación > 0,15 ATR": sep > 0.15, "separación > 0,3 ATR": sep > 0.3,
        "ER > 0,3": er > 0.3, "ER > 0,4": er > 0.4,
        "CHOP < 50": chop < 50, "CHOP < 45": chop < 45,
        "sin cruces en 1 h": prev_x(12) == 0, "sin cruces en 2 h": prev_x(24) == 0,
        "caja 2 h > 0,25 ATR diario": box24 > 0.25 * datr_bar, "caja 2 h > 0,35 ATR diario": box24 > 0.35 * datr_bar,
    }
    day = np.where(rth, gday, -1)
    last = hm == 955
    can = (hm >= 570) & (hm <= 930)
    exits = {"cruce contrario": (0.0, 0.0, True), "1,5 ATR + cruce": (1.5, 0.0, True), "3 ATR + 3R": (3.0, 3.0, False)}
    to_year = lambda x: x.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for (fn, rok), et, fl, (xn, (sm, rr, xc)) in itertools.product(filters.items(), (0, 1), (0, 1), exits.items()):
        pnl, dd = sim(o, h, l, c, e9, e21, atr, rok, fvw, day, can, last, et, fl, sm, rr, xc, 3, COST)
        if len(pnl) < 50:
            continue
        y = to_year(dd)
        u = pnl * USD
        r = dict(filtro_rango=fn, entrada=["cruce", "retroceso"][et], vwap="sí" if fl else "no", salida=xn)
        for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
            vv = u[sel]
            gg, ls = vv[vv > 0].sum(), -vv[vv < 0].sum()
            eq = np.cumsum(vv)
            r |= {f"{nm_}_ops": round(len(vv) / yrs), f"{nm_}_usd": round(vv.sum() / yrs), f"{nm_}_pf": round(gg / ls, 2),
                  f"{nm_}_pts_op": round(vv.mean() / USD, 2)}
            if nm_ == "val":
                r |= dict(val_dd=round((np.maximum.accumulate(eq) - eq).max()), val_win=round((vv > 0).mean(), 2))
        by = pd.Series(u).groupby(y).sum()
        r["años"] = f"{(by > 0).sum()}/{len(by)}"
        r["by_year"] = by.round().astype(int).to_dict()
        rows.append(r)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/ema921_rango.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(f"══════ EMA 9/21 en 5 min con filtros de rango, NQ: {len(R)} variantes ══════")
    print(R.groupby("filtro_rango", sort=False).apply(lambda x: pd.Series({
        "n": len(x), "% ambos": both(x), "med dev $": int(x.dev_usd.median()), "med val $": int(x.val_usd.median()),
        "med PF dev": x.dev_pf.median(), "med PF val": x.val_pf.median(), "med pts/op val": x.val_pts_op.median(),
        "ops/año": int(x.val_ops.median())}), include_groups=False).to_string())
    cols = [k for k in R.columns if k != "by_year"]
    print("\nLas 15 con el peor periodo más alto:")
    S = R.assign(mn=R[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
    print(S.head(15)[cols].to_string(index=False))
    print("\nLas 10 con mejor PF mínimo (≥ 60 operaciones/año):")
    P = R[R.val_ops >= 60].assign(pfm=R[["dev_pf", "val_pf"]].min(axis=1)).sort_values("pfm", ascending=False)
    print(P.head(10)[cols].to_string(index=False))
    for _, x in S.head(3).iterrows():
        print(x.filtro_rango, x.entrada, x.vwap, x.salida, x.by_year)


if __name__ == "__main__":
    main()
