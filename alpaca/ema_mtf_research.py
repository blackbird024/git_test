"""Cruce de EMAs más intradía (5 y 15 min) en NQ / MNQ, a favor de la tendencia de 1 hora.

En ema_cross_research.py el cruce en 5 y 15 min no tenía ventaja por sí solo. Aquí se prueba si la tiene
cuando solo se opera a favor de las EMAs de 1 hora, en ciertas franjas de la sesión de NY y con stop/objetivo.
Mismos datos y método: se ELIGE con 2018-2022, se JUZGA con 2023-2026, control en ES; coste 1 punto; 1 MNQ.

Variantes:
  tf        5 min / 15 min (temporalidad del cruce)
  emas      pares rápidos para el cruce
  filtro1h  ninguno / EMA 12-26 de 1 h / EMA 20-50 de 1 h (solo cruces en la dirección de la tendencia de 1 h)
  franja    9:30-11:30 / 9:30-15:30 (horas en que se aceptan entradas; todo cerrado a las 16:00)
  salida    cruce contrario · stop 1 ATR + objetivo 2R · stop 1,5 ATR + cruce contrario
  máximo    1 o 3 operaciones por día

Uso:
    python ema_mtf_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m
from ema_cross_research import COST, SPLIT, USD, align, tf_frame

PAIRS = [(5, 13), (8, 21), (9, 21), (12, 26), (20, 50)]
HTF = {"-": None, "1h 12/26": (12, 26), "1h 20/50": (20, 50)}
EXITS = {"cruce": (0.0, 0.0), "1ATR+2R": (1.0, 2.0), "1.5ATR+cruce": (1.5, 0.0)}


@njit(cache=True)
def sim(o, h, l, c, st, htf, atr, day, can, last, stopm, rr, maxn, cost):
    n = len(o)
    pnl = np.empty(n)
    dd = np.empty(n, np.int64)
    nt, pos, e, stop, tgt, cnt = 0, 0, 0.0, 0.0, 0.0, 0
    for i in range(1, n - 1):
        newday = day[i] != day[i - 1]
        if newday:
            cnt = 0
            if pos != 0:
                pnl[nt] = pos * (c[i - 1] - e) - cost
                dd[nt] = day[i - 1]
                nt += 1
                pos = 0
        cross = (not newday) and st[i] != st[i - 1] and st[i] != 0
        if pos != 0:
            out = 0.0
            done = False
            if stopm > 0 and ((pos == 1 and l[i] <= stop) or (pos == -1 and h[i] >= stop)):
                out = min(stop, o[i]) if pos == 1 else max(stop, o[i])
                done = True
            elif rr > 0 and ((pos == 1 and h[i] >= tgt) or (pos == -1 and l[i] <= tgt)):
                out = max(tgt, o[i]) if pos == 1 else min(tgt, o[i])
                done = True
            elif last[i]:
                out = c[i]
                done = True
            elif rr == 0 and st[i] != pos:
                out = o[i + 1]
                done = True
            if done:
                pnl[nt] = pos * (out - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
        if pos == 0 and cross and can[i] and not last[i] and cnt < maxn:
            want = int(st[i])
            if htf[i] != 0 and htf[i] != want:
                continue
            pos = want
            cnt += 1
            e = o[i + 1]
            risk = stopm * atr[i]
            stop = e - pos * risk
            tgt = e + pos * rr * risk
    return pnl[:nt], dd[:nt]


def run(sym):
    df = load_5m(sym)
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    ny = (hm >= 570) & (hm < 960)
    idx = np.flatnonzero(ny)
    last = (hm == 955)[idx]
    cans = {"9:30-11:30": ((hm >= 570) & (hm < 690))[idx], "9:30-15:30": ((hm >= 570) & (hm <= 930))[idx]}
    o, h, l, c = (df[k].to_numpy()[idx] for k in ("open", "high", "low", "close"))
    day = gday[idx]
    b1 = tf_frame(df, 60)
    htf = {"-": np.zeros(len(idx))}
    for k, p in HTF.items():
        if p:
            b1[k] = np.sign(b1.close.ewm(span=p[0], adjust=False).mean() - b1.close.ewm(span=p[1], adjust=False).mean())
            htf[k] = np.nan_to_num(align(df, b1, [k])[k])[idx]
    low = {}
    for tfn, tf in (("5m", 5), ("15m", 15)):
        b = tf_frame(df, tf)
        for f, s in PAIRS:
            b[f"{f}/{s}"] = np.sign(b.close.ewm(span=f, adjust=False).mean() - b.close.ewm(span=s, adjust=False).mean())
        A = align(df, b, ["atr"] + [f"{f}/{s}" for f, s in PAIRS])
        low[tfn] = {k: np.nan_to_num(v)[idx] for k, v in A.items()}
    to_year = lambda dd: dd.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for tfn, (f, s), hk, ck, ek, mx in itertools.product(low, PAIRS, HTF, cans, EXITS, (1, 3)):
        sm, rr = EXITS[ek]
        pnl, dd = sim(o, h, l, c, low[tfn][f"{f}/{s}"], htf[hk], low[tfn]["atr"], day, cans[ck], last, sm, rr, mx, COST)
        if len(pnl) < 50:
            continue
        y = to_year(dd)
        u = pnl * USD
        r = dict(tf=tfn, emas=f"{f}/{s}", filtro1h=hk, franja=ck, salida=ek, max_dia=mx)
        for name, sel, yrs in (("dev", y < SPLIT, 5), ("val", y >= SPLIT, 3.75)):
            v = u[sel]
            g, ls = v[v > 0].sum(), -v[v < 0].sum()
            eq = np.cumsum(v)
            r.update({f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs), f"{name}_pf": round(g / ls, 2)})
            if name == "val":
                r.update(val_dd=round((np.maximum.accumulate(eq) - eq).max()), val_win=round((v > 0).mean(), 2))
        by = pd.Series(u).groupby(y).sum()
        r["años_pos"] = f"{(by > 0).sum()}/{len(by)}"
        r["by_year"] = by.round().astype(int).to_dict()
        rows.append(r)
    return pd.DataFrame(rows)


def report(r, sym):
    print(f"\n══════════ {sym}: $/año por 1 MNQ · desarrollo 2018-2022 · validación 2023-2026 ══════════")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    for col in ("tf", "filtro1h", "franja", "salida", "max_dia"):
        print(r.groupby(col).apply(lambda x: pd.Series({"variantes": len(x), "% gana ambos": both(x),
                                                       "mediana dev": int(x.dev_usd.median()),
                                                       "mediana val": int(x.val_usd.median())}), include_groups=False).to_string(), "\n")
    cols = [c for c in r.columns if c != "by_year"]
    print("Mejor de cada temporalidad ELEGIDA con 2018-2022 → 2023-2026:")
    print(r.loc[r.groupby("tf").dev_usd.idxmax(), cols].to_string(index=False))
    print("\nLas 15 con el peor periodo más alto:")
    r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1))
    print(r.sort_values("minimo", ascending=False).head(15)[cols].to_string(index=False))


def main():
    pd.set_option("display.width", 250)
    for sym in ("NQ", "ES"):
        r = run(sym)
        r.to_pickle(f".lab_cache/ema_mtf_{sym}.pkl")
        report(r, sym)


if __name__ == "__main__":
    main()
