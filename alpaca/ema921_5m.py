"""EMA 9/21 en velas de 5 min en NQ / MNQ: búsqueda a fondo de una versión que funcione.

En ema_cross_research.py el cruce 9/21 de 5 min solo ganaba con PF ~1,05 (inoperable). Aquí se prueban las
formas habituales de mejorarlo:
  entrada   cruce (la vela cierra con la 9 cruzando la 21) · retroceso (con la 9 por encima de la 21, el precio
            toca la EMA 9 y cierra por encima de la 21 → a favor; espejo en cortos)
  filtro    ninguno · tendencia de 1 h (EMA 9/21 de 1 h) · lado de la VWAP de Globex · ambos
  franja    9:30-11:30 · 10:00-15:30 · 9:30-15:30 (hora NY; todo cerrado a las 16:00)
  salida    cruce contrario · stop 1,5 ATR + objetivo 2R · stop 1,5 ATR + cruce · stop 3 ATR + objetivo 3R
            (ATR 14 de velas de 5 min)
  máximo    1 o 3 operaciones por día
Datos: NQ 1 min con volumen 2018 - oct 2026 agrupado en 5 min. Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.
Coste 1 punto por operación; resultados por 1 MNQ.

Uso:
    python ema921_5m.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from ema_cross_research import align, tf_frame

COST, USD = 1.0, 2.0


@njit(cache=True)
def sim(o, h, l, c, e9, e21, atr, f1h, fvw, day, can, last, etype, filt, stopm, rr, xcross, maxn, cost):
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
        if pos != 0 or not can[i] or last[i] or cnt >= maxn:
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
        if (filt == 1 or filt == 3) and f1h[i] != sig:
            continue
        if (filt == 2 or filt == 3) and fvw[i] != sig:
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
    e9 = b.close.ewm(span=9, adjust=False).mean().to_numpy()
    e21 = b.close.ewm(span=21, adjust=False).mean().to_numpy()
    pc = np.r_[c[0], c[:-1]]
    atr = pd.Series(np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))).rolling(14).mean().bfill().to_numpy()
    typ = (h + l + c) / 3
    v = b.volume.to_numpy().astype(float)
    g = pd.Series(gday)
    vw = (pd.Series(typ * v).groupby(g).cumsum() / pd.Series(v).groupby(g).cumsum().replace(0, np.nan)).to_numpy()
    fvw = np.where(c > vw, 1, -1)
    hb = tf_frame(b[["open", "high", "low", "close"]], 60)
    hb["s"] = np.sign(hb.close.ewm(span=9, adjust=False).mean() - hb.close.ewm(span=21, adjust=False).mean())
    f1h = np.nan_to_num(align(b, hb, ["s"])["s"]).astype(np.int64)
    rth = (hm >= 570) & (hm < 960)
    day = np.where(rth, gday, -1)
    last = hm == 955
    wins = {"9:30-11:30": (hm >= 570) & (hm < 690), "10:00-15:30": (hm >= 600) & (hm <= 930), "9:30-15:30": (hm >= 570) & (hm <= 930)}
    exits = {"cruce contrario": (0.0, 0.0, True), "1,5 ATR + 2R": (1.5, 2.0, False), "1,5 ATR + cruce": (1.5, 0.0, True),
             "3 ATR + 3R": (3.0, 3.0, False)}
    to_year = lambda x: x.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for et, fl, (wn, can), (xn, (sm, rr, xc)), mx in itertools.product((0, 1), (0, 1, 2, 3), wins.items(), exits.items(), (1, 3)):
        pnl, dd = sim(o, h, l, c, e9, e21, atr, f1h, fvw, day, can, last, et, fl, sm, rr, xc, mx, COST)
        if len(pnl) < 50:
            continue
        y = to_year(dd)
        u = pnl * USD
        r = dict(entrada=["cruce", "retroceso"][et], filtro=["-", "1h 9/21", "VWAP", "1h + VWAP"][fl], franja=wn, salida=xn, max_dia=mx)
        for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
            vv = u[sel]
            gg, ls = vv[vv > 0].sum(), -vv[vv < 0].sum()
            eq = np.cumsum(vv)
            r |= {f"{nm_}_ops": round(len(vv) / yrs), f"{nm_}_usd": round(vv.sum() / yrs), f"{nm_}_pf": round(gg / ls, 2),
                  f"{nm_}_win": round((vv > 0).mean(), 2)}
            if nm_ == "val":
                r["val_dd"] = round((np.maximum.accumulate(eq) - eq).max())
        by = pd.Series(u).groupby(y).sum()
        r["años"] = f"{(by > 0).sum()}/{len(by)}"
        r["by_year"] = by.round().astype(int).to_dict()
        rows.append(r)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/ema921_5m.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(f"══════ EMA 9/21 en 5 min, NQ: {len(R)} variantes · ganan en ambos periodos: {both(R)} ══════")
    for col in ("entrada", "filtro", "franja", "salida", "max_dia"):
        print(R.groupby(col).apply(lambda x: pd.Series({"n": len(x), "% ambos": both(x), "med dev": int(x.dev_usd.median()),
              "med val": int(x.val_usd.median()), "med PF val": x.val_pf.median()}), include_groups=False).to_string(), "\n")
    cols = [k for k in R.columns if k != "by_year"]
    print("Mejor ELEGIDA con 2018-2022:")
    print(R.loc[[R.dev_usd.idxmax()], cols].to_string(index=False))
    print("\nLas 15 con el peor periodo más alto:")
    S = R.assign(mn=R[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
    print(S.head(15)[cols].to_string(index=False))
    for _, x in S.head(3).iterrows():
        print(x.entrada, x.filtro, x.franja, x.salida, x.max_dia, x.by_year)


if __name__ == "__main__":
    main()
