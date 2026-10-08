"""Volumen en NQ / MNQ (datos de 1 min con volumen, Databento, 2018 - oct 2026; el oro no tiene volumen histórico aquí).

1) ORB 5 min filtrado por volumen relativo (RVOL) de la primera vela: volumen de la vela 9:30-9:35 dividido por la
   media de esa misma vela en los 14 días anteriores. Mismas reglas del ORB 5 min (dirección de la primera vela,
   entrada 9:35, stop 10 % del ATR de la sesión, cierre 16:00). Grupos: RVOL < 0,8 · 0,8-1,2 · 1,2-1,6 · > 1,6.
2) Vela de volumen extremo (5 min): volumen ≥ k × la media de esa hora en los 20 días anteriores (k = 2, 3, 4),
   entre 9:40 y 15:00 NY. Entrada en la apertura siguiente a favor de la vela (impulso) o en contra (agotamiento).
   Stop 0,1 ATR diario, objetivo 1R / 2R / cierre 16:00.
Coste 1 punto (2 $/punto por MNQ). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python volumen_test.py
"""

import itertools

import numpy as np
import pandas as pd

import vwap_globex_8y as V
from alto_acierto_simple import bracket
from nq_intraday_research import build_days
from soportes_trendlines import sim


def stats(rows, name, yrs, u, **kw):
    u, yrs = np.asarray(u, float), np.asarray(yrs)
    m = np.isfinite(u)
    u, yrs = u[m], yrs[m]
    if len(u) < 40:
        return
    dv, vv = u[yrs < 2023], u[yrs >= 2023]
    pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
    eq = np.cumsum(u)
    rows.append(dict(prueba=name, **kw, ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2), dev=round(dv.sum() / 5),
                     pf_dev=pf(dv), val=round(vv.sum() / 3.75), pf_val=pf(vv), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                     años=f"{sum(u[yrs == y].sum() > 0 for y in range(2018, 2027))}/9"))


def main():
    pd.set_option("display.width", 250)
    m1 = V.load()
    m1.index = m1.index.tz_convert("America/New_York")
    b = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    t = b.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    o, h, l, c, v = (b[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    rows = []
    # 1) ORB 5 min por RVOL
    first = b[hm == 570].volume
    first.index = first.index.normalize().tz_localize(None)
    rvol = (first / first.rolling(14).mean().shift(1))
    days = build_days("NQ")
    res = []
    for x in days:
        d = pd.Timestamp(x["d"])
        if d not in rvol.index or not np.isfinite(rvol[d]):
            continue
        B = x["rth"]
        s = int(np.sign(B[0, 3] - B[0, 0]))
        if s == 0:
            continue
        e = B[1, 0]
        px = bracket(B, 1, s, e, e - s * 0.1 * x["atr"], e + s * 1e9)
        res.append((d.year, rvol[d], (s * (px - e) - 1) * 2))
    R = pd.DataFrame(res, columns=["y", "rv", "u"])
    for lo, hi in ((0, 0.8), (0.8, 1.2), (1.2, 1.6), (1.6, 99), (0, 99), (1.2, 99)):
        g = R[(R.rv >= lo) & (R.rv < hi)]
        stats(rows, "ORB 5 min por RVOL", g.y, g.u, filtro=f"RVOL {lo}-{hi if hi < 99 else '∞'}")
    # 2) velas de volumen extremo
    tod = pd.Series(v, index=t)
    avg = tod.groupby(hm).transform(lambda s: s.rolling(20).mean().shift(1)).to_numpy()
    gd = (t + pd.Timedelta(hours=6)).normalize()
    D = b.groupby(gd).agg(high=("high", "max"), low=("low", "min"))
    atr = (D.high - D.low).rolling(14).mean().shift(1).reindex(gd).to_numpy()
    day = np.array(t.normalize().asi8)
    eod = pd.Series(np.where(hm < 960, np.arange(len(t)), -1)).groupby(day).max().reindex(day).to_numpy().astype(np.int64)
    for k_, mode, rr in itertools.product((2, 3, 4), ("impulso", "agotamiento"), (1.0, 2.0, 0.0)):
        sig = np.flatnonzero((v >= k_ * avg) & (hm >= 580) & (hm <= 895) & (c != o) & np.isfinite(atr))
        ke = sig + 1
        ok = (ke < len(t)) & (eod[np.minimum(ke, len(t) - 1)] > ke)
        sig, ke = sig[ok], ke[ok]
        side = np.sign(c[sig] - o[sig]).astype(np.int64) * (1 if mode == "impulso" else -1)
        u = sim(h, l, o, c, ke.astype(np.int64), side, o[ke], 0.1 * atr[ke], eod[ke], rr if rr else 1e6, 1.0, 2.0)
        stats(rows, "vela de volumen extremo", t.year.to_numpy()[ke], u, filtro=f"vol ≥ {k_}× · {mode} · {'cierre' if not rr else f'{rr:g}R'}")
    Rr = pd.DataFrame(rows)
    Rr.to_pickle(".lab_cache/volumen_test.pkl")
    print(Rr.to_string(index=False))


if __name__ == "__main__":
    main()
