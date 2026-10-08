"""Mezclar: las 3 estrategias buenas + un filtro (o dos) que tiene que estar de acuerdo. NQ y oro, 2018 - oct 2026.

Estrategias base (1 micro, mismas reglas que en topstep_sim.py):
  ORB 5 min NQ        dirección de la vela 9:30-9:35, entrada 9:35, stop 10 % del ATR de la sesión, cierre 16:00
  NQ rango de ayer    ruptura del máximo/mínimo de ayer (9:30-16:00) si abre dentro, stop en el medio, cierre 16:00
  Oro Londres         ruptura del rango de NY de ayer desde las 08:00 Londres, stop al otro lado, objetivo 1×rango,
                      entradas hasta 12:00 Londres, cierre 14:25 Londres
Filtros (calculados con lo que se sabe en el momento de decidir: 9:30 NY para NQ, 08:00 Londres para el oro).
La operación se hace solo si el filtro va en la MISMA dirección que la operación (o, como control, en la contraria):
  noche        el precio está por encima/debajo de la apertura de Globex (18:00 NY)
  ayer         la sesión de NY de ayer cerró alcista/bajista (cierre vs apertura)
  diario SMA20 el precio está por encima/debajo de la media de 20 cierres diarios
  EMA50 1h     el precio está por encima/debajo de la EMA 50 de 1 h
  RSI 1h       RSI 14 de 1 h por encima/debajo de 50
  EMA 9/21 15m la EMA 9 de 15 min por encima/debajo de la EMA 21
  hueco        (solo NQ) la apertura de las 9:30 por encima/debajo del cierre de ayer
También todas las parejas de filtros (los dos de acuerdo).
Coste NQ 1 punto (2 $/punto) · oro 0,3 puntos (10 $/punto). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python mezcla_filtros.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).to_numpy()


def context(df):
    """Para cada vela de 5 min k: valores de los indicadores conocidos al ABRIR k (hasta el cierre de k-1)."""
    t = df.index
    c = df.close.to_numpy()
    n = len(t)

    def on5(b, vals, tfm):
        kk = np.searchsorted(t.asi8, (b.index + pd.Timedelta(minutes=tfm)).asi8)   # primera vela de 5 min tras cerrar
        pos = np.searchsorted(kk, np.arange(n), side="right") - 1
        return np.where(pos >= 0, vals[np.maximum(pos, 0)], np.nan)

    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    h1 = df.resample("60min").agg(agg).dropna()
    m15 = df.resample("15min").agg(agg).dropna()
    gd = (t + pd.Timedelta(hours=6)).normalize()
    D = df.groupby(gd).agg(open=("open", "first"), close=("close", "last"))
    sma = D.close.rolling(20).mean().shift(1).reindex(gd).to_numpy()
    g_open = D.open.reindex(gd).to_numpy()
    prev_c = np.r_[np.nan, c[:-1]]
    e9 = on5(m15, m15.close.ewm(span=9, adjust=False).mean().to_numpy(), 15)
    e21 = on5(m15, m15.close.ewm(span=21, adjust=False).mean().to_numpy(), 15)
    return {"noche": np.sign(prev_c - g_open),
            "diario SMA20": np.sign(prev_c - sma),
            "EMA50 1h": np.sign(prev_c - on5(h1, h1.close.ewm(span=50, adjust=False).mean().to_numpy(), 60)),
            "RSI 1h": np.sign(on5(h1, rsi(h1.close.to_numpy()), 60) - 50),
            "EMA 9/21 15m": np.sign(e9 - e21)}


def nq_trades():
    df = load_5m("NQ")
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    ctx = context(df)
    groups = pd.Series(np.arange(len(df))).groupby(np.array(t.normalize().asi8)).indices
    days = []
    for d in sorted(groups):
        idx = np.asarray(groups[d])
        rth = idx[(hm[idx] >= 570) & (hm[idx] < 960)]
        days.append(rth if len(rth) == 78 else None)
    rng = [np.nan if r is None else h[r].max() - l[r].min() for r in days]
    atr = pd.Series(rng).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    out = {"ORB 5 min NQ": [], "NQ rango de ayer": []}
    for i in range(1, len(days)):
        r, p = days[i], days[i - 1]
        if r is None or p is None or not np.isfinite(atr[i]):
            continue
        k0 = r[0]
        f = {k: v[k0] for k, v in ctx.items()}
        f["ayer"] = np.sign(c[p[-1]] - o[p[0]])
        f["hueco"] = np.sign(o[k0] - c[p[-1]])
        y = t[k0].year
        # ORB 5 min
        s = int(np.sign(c[r[0]] - o[r[0]]))
        if s:
            e, sl = o[r[1]], o[r[1]] - s * 0.1 * atr[i]
            px = c[r[-1]]
            for q in r[1:]:
                if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                    px = sl
                    break
            out["ORB 5 min NQ"].append((y, s, (s * (px - e) - 1) * 2, f))
        # rango de ayer
        ph, pl = h[p].max(), l[p].min()
        mid = (ph + pl) / 2
        if pl <= o[k0] <= ph:
            for j, k in enumerate(r[:73]):
                if h[k] > ph:
                    s, e = 1, max(ph, o[k])
                elif l[k] < pl:
                    s, e = -1, min(pl, o[k])
                else:
                    continue
                px = c[r[-1]]
                for q in r[j + 1:]:
                    if (s == 1 and l[q] <= mid) or (s == -1 and h[q] >= mid):
                        px = min(mid, o[q]) if s == 1 else max(mid, o[q])
                        break
                out["NQ rango de ayer"].append((y, s, (s * (px - e) - 1) * 2, f))
                break
    return out


def gold_trades():
    import liquidez_ruptura_london as GL
    df = load_5m("GC")
    ctx = context(df)
    days, o, h, l, c = GL.build("GC")
    out, prev_ny = [], None
    for x in days:
        H, L = x["ref"]["ayer NY"]
        R = H - L
        seg, segl = x["s"][x["sl"] < 865], x["sl"][x["sl"] < 865]
        if prev_ny is None:
            prev_ny = x["ny"]
            continue
        f = {k: v[seg[0]] for k, v in ctx.items()} if len(seg) else {}
        f["ayer"] = np.sign(c[prev_ny[-1]] - o[prev_ny[0]])
        prev_ny = x["ny"]
        if R <= 0 or len(seg) < 10 or not (L < o[seg[0]] < H):
            continue
        for j, k in enumerate(seg):
            if segl[j] > 720:
                break
            up, dn = h[k] > H, l[k] < L
            if not (up or dn):
                continue
            if up and dn:
                break
            s = 1 if up else -1
            e = max(H, o[k]) if s == 1 else min(L, o[k])
            sl = L if s == 1 else H
            tg = (H if s == 1 else L) + s * R
            px = c[seg[-1]]
            if (s == 1 and l[k] <= sl) or (s == -1 and h[k] >= sl):
                px = sl
            else:
                for q in seg[j + 1:]:
                    if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                        px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                        break
                    if (s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg):
                        px = tg
                        break
            out.append((x["d"].year, s, (s * (px - e) - 0.3) * 10, f))
            break
    return {"Oro Londres": out}


def row(name, filt, T):
    if len(T) < 60:
        return None
    y = np.array([a[0] for a in T])
    u = np.array([a[2] for a in T])
    d, v = u[y < 2023], u[y >= 2023]
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = np.cumsum(u)
    return dict(estrategia=name, filtro=filt, ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2),
                dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                peor_racha=round((np.maximum.accumulate(eq) - eq).max()), años=f"{sum(u[y == k].sum() > 0 for k in range(2018, 2027))}/9")


def main():
    pd.set_option("display.width", 250)
    trades = {**nq_trades(), **gold_trades()}
    rows = []
    for name, T in trades.items():
        keys = sorted({k for a in T for k in a[3]})
        rows.append(row(name, "— (sin filtro)", T))
        for k in keys:
            rows.append(row(name, f"{k} a favor", [a for a in T if a[3].get(k) == a[1]]))
            rows.append(row(name, f"{k} en contra", [a for a in T if a[3].get(k) == -a[1]]))
        for k1, k2 in itertools.combinations(keys, 2):
            rows.append(row(name, f"{k1} + {k2} a favor", [a for a in T if a[3].get(k1) == a[1] and a[3].get(k2) == a[1]]))
    R = pd.DataFrame([r for r in rows if r])
    R.to_pickle(".lab_cache/mezcla_filtros.pkl")
    for name, g in R.groupby("estrategia", sort=False):
        base = g.iloc[0]
        print(f"\n══ {name} · sin filtro: acierto {base.acierto:.0%}, dev {base.dev}, val {base.val}, racha {base.peor_racha} ══")
        print(g.sort_values("acierto", ascending=False).drop(columns="estrategia").to_string(index=False))


if __name__ == "__main__":
    main()
