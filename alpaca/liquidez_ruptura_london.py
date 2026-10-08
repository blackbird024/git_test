"""Ruptura de la liquidez de sesión en la APERTURA DE LONDRES (NQ y oro, 2018 - oct 2026).

Igual que liquidez_ruptura.py pero la sesión operada es Londres (hora de Londres):
Rangos: Asia (00:00-06:00 Londres) · noche (18:00 NY del día anterior → 08:00 Londres) · ayer NY (9:30-16:00 NY).
Solo si a las 08:00 Londres el precio está DENTRO del rango. Orden STOP en máximo y mínimo; la primera, una al día.
Entradas hasta 10:00 o 12:00 Londres. Stop: medio · otro lado. Objetivo: 0,5×rango · 1×rango · ninguno.
Salida: 12:00 Londres · 14:25 Londres (antes de NY) · 16:00 NY (cierre de NY).
Coste NQ 1 punto (2 $/punto) · oro 0,3 puntos (10 $/punto). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python liquidez_ruptura_london.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def build(sym):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gd = np.array((tn + pd.Timedelta(hours=6)).normalize().date)
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    lm = np.where(np.array(tl.date) < gd, lm - 1440, lm)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    nm = np.where(nm >= 1080, nm - 1440, nm)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    days, prev = [], None
    for d, idx in pd.Series(np.arange(len(df))).groupby(gd).indices.items():
        idx = np.asarray(idx)
        L, N = lm[idx], nm[idx]
        asia, night = idx[(L >= 0) & (L < 360)], idx[L < 480]
        sess = idx[(L >= 480) & (N < 960)]
        nyr = idx[(N >= 570) & (N < 960)]
        if len(asia) < 50 or len(sess) < 100 or len(nyr) < 70:
            prev = None
            continue
        x = dict(d=pd.Timestamp(d), s=sess, sl=L[(L >= 480) & (N < 960)], sn=N[(L >= 480) & (N < 960)], ny=nyr,
                 ref={"Asia": (h[asia].max(), l[asia].min()), "noche": (h[night].max(), l[night].min())})
        if prev is not None:
            x["ref"]["ayer NY"] = (h[prev["ny"]].max(), l[prev["ny"]].min())
            days.append(x)
        prev = x
    return days, o, h, l, c


def run(days, o, h, l, c, ref, last_entry, stop, tgt, ex, cost, usd):
    res = []
    for x in days:
        H, L = x["ref"][ref]
        R, mid = H - L, (H + L) / 2
        s_idx, sl_m, sn_m = x["s"], x["sl"], x["sn"]
        if ex == "16:00 NY":
            keep = np.ones(len(s_idx), bool)
        else:
            keep = sl_m < (720 if ex == "12:00 Lon" else 865)
        seg, segl = s_idx[keep], sl_m[keep]
        if R <= 0 or len(seg) < 10 or not (L < o[seg[0]] < H):
            continue
        for j, k in enumerate(seg):
            if segl[j] > last_entry:
                break
            up, dn = h[k] > H, l[k] < L
            if not (up or dn):
                continue
            if up and dn:
                break
            s = 1 if up else -1
            e = max(H, o[k]) if s == 1 else min(L, o[k])
            sl = mid if stop == "medio" else (L if s == 1 else H)
            tg = None if tgt == 0 else (H if s == 1 else L) + s * tgt * R
            px = c[seg[-1]]
            if (s == 1 and l[k] <= sl) or (s == -1 and h[k] >= sl):
                px = sl
            else:
                for q in seg[j + 1:]:
                    if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                        px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                        break
                    if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                        px = tg
                        break
            res.append((x["d"].year, (s * (px - e) - cost) * usd, abs(e - sl) * usd))
            break
    return pd.DataFrame(res, columns=["y", "u", "riesgo"])


def main():
    pd.set_option("display.width", 260)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        days, o, h, l, c = build(sym)
        for ref, le, stop, tgt, ex in itertools.product(("Asia", "noche", "ayer NY"), (600, 720), ("medio", "otro lado"), (0.5, 1.0, 0),
                                                        ("12:00 Lon", "14:25 Lon", "16:00 NY")):
            if ex == "12:00 Lon" and le == 720:
                continue
            R = run(days, o, h, l, c, ref, le, stop, tgt, ex, cost, usd)
            if len(R) < 50:
                continue
            d, v = R[R.y < 2023].u, R[R.y >= 2023].u
            pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
            eq = R.u.cumsum()
            rows.append(dict(activo=sym, rango=ref, entradas_hasta=f"{le // 60}:00 Lon", stop=stop,
                             objetivo={0.5: "0,5×rango", 1.0: "1×rango", 0: "cierre"}[tgt], salida=ex, ops_año=round(len(R) / 8.75),
                             acierto=round((R.u > 0).mean(), 2), riesgo_med=round(R.riesgo.median()),
                             dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                             peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9",
                             por_año=R.groupby("y").u.sum().round().astype(int).to_dict()))
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/liquidez_ruptura_london.pkl")
    cols = [k for k in R.columns if k != "por_año"]
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(R.groupby(["activo", "rango", "salida"]).apply(both, include_groups=False).unstack().to_string())
    print(R.groupby(["activo", "stop"]).apply(both, include_groups=False).unstack().to_string())
    S = R.assign(mn=R[["dev", "val"]].min(axis=1)).sort_values("mn", ascending=False)
    print("\nMejores:")
    print(S.head(14)[cols].to_string(index=False))
    for _, x in S.head(3).iterrows():
        print(x.activo, x.rango, x.stop, x.objetivo, x.salida, x.entradas_hasta, x.por_año)


if __name__ == "__main__":
    main()
