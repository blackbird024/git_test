"""Fair Value Gaps (FVG) por sí solos: cuando el precio vuelve al hueco, ¿rebota o lo atraviesa? NQ y oro, 2018 - oct 2026.

FVG alcista en velas de 5 min, 15 min o 1 h: mínimo de la vela 3 > máximo de la vela 1 (hueco = [máx 1, mín 3]).
Bajista: espejo. Tamaño mínimo: todos · ≥ 0,05 ATR diario · ≥ 0,1 ATR diario. El FVG vale hasta el cierre de las 16:00 NY.
Evento: primer regreso del precio (vela de 5 min) al borde cercano del FVG entre 3:00 y 15:00 NY.
Entradas (orden límite):
  borde   en el borde cercano          ce   en el 50 % del FVG (si llega; si no, no hay operación)
Dirección: a favor del FVG (rebote, lo que enseña ICT) · en contra (control / «inversion FVG»).
Stop: al otro lado del FVG (más 1 tick) · o s · ATR diario (0,1). Objetivo 1R · 2R. Cierre forzoso 16:00 NY.
Una operación a la vez. Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python fvg_test.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m
from soportes_trendlines import sim


@njit(cache=True)
def retest(h5, l5, start, end, lvl, side):
    """Primera vela en [start, end] que llega a lvl (side=+1: el precio baja hasta lvl; −1: sube)."""
    for k in range(start, end + 1):
        if (side == 1 and l5[k] <= lvl) or (side == -1 and h5[k] >= lvl):
            return k
    return -1


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd, tick in (("NQ", 1.0, 2.0, 0.25), ("GC", 0.3, 10.0, 0.1)):
        d5 = load_5m(sym)
        t5 = d5.index
        o5, h5, l5, c5 = (d5[k].to_numpy() for k in ("open", "high", "low", "close"))
        m5 = (t5.hour * 60 + t5.minute).to_numpy()
        gd = (t5 + pd.Timedelta(hours=6)).normalize()
        D = d5.groupby(gd).agg(high=("high", "max"), low=("low", "min"))
        atr5 = (D.high - D.low).rolling(14).mean().shift(1).reindex(gd).to_numpy()
        day5 = np.array(t5.normalize().asi8)
        eod = pd.Series(np.where(m5 < 960, np.arange(len(t5)), -1)).groupby(day5).max().reindex(day5).to_numpy()
        inwin = (m5 >= 180) & (m5 <= 900)
        for tf, rule in (("5m", None), ("15m", "15min"), ("1h", "60min")):
            b = d5 if rule is None else d5.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            bh, bl = b.high.to_numpy(), b.low.to_numpy()
            tfm = {"5m": 5, "15m": 15, "1h": 60}[tf]
            ks = np.searchsorted(t5.asi8, (b.index + pd.Timedelta(minutes=tfm)).asi8)   # primera vela de 5 min tras la 3.ª vela
            fv = []
            for i in range(2, len(b)):
                k0 = ks[i]
                if k0 >= len(t5) or not inwin[k0] or eod[k0] <= k0 or not np.isfinite(atr5[k0]):
                    continue
                if bl[i] > bh[i - 2]:
                    fv.append((k0, 1, bh[i - 2], bl[i], (bl[i] - bh[i - 2]) / atr5[k0]))   # alcista: lo, hi
                elif bh[i] < bl[i - 2]:
                    fv.append((k0, -1, bh[i], bl[i - 2], (bl[i - 2] - bh[i]) / atr5[k0]))
            F = np.array(fv)
            yr5 = t5.year.to_numpy()
            pre = {}
            for entry in ("borde", "ce"):
                lv = np.where(F[:, 1] == 1, F[:, 3], F[:, 2]) if entry == "borde" else (F[:, 2] + F[:, 3]) / 2
                kr = np.array([retest(h5, l5, int(k0), int(min(eod[int(k0)], len(t5) - 1)), x, int(sd))
                               for k0, sd, x in zip(F[:, 0], F[:, 1], lv)])
                pre[entry] = (lv, kr)
            for minsz, entry, stopm, mode, rr in itertools.product((0.0, 0.05, 0.1), ("borde", "ce"), ("otro lado", "0,1 ATR"),
                                                                   ("a favor", "en contra"), (1.0, 2.0)):
                lv, kr = pre[entry]
                sel = (F[:, 4] >= minsz) & (kr >= 0)
                sel[sel] &= inwin[kr[sel]]
                kk = kr[sel].astype(np.int64)
                side = F[sel, 1].astype(np.int64)
                s_ = side if mode == "a favor" else -side
                far = np.where(side == 1, F[sel, 2] - tick, F[sel, 3] + tick)
                risk = np.abs(lv[sel] - far) if stopm == "otro lado" else 0.1 * atr5[kk]
                g = risk > 0
                K, S, E, Rk = kk[g], s_[g], lv[sel][g], risk[g]
                Y = yr5[K]
                if len(K) < 80:
                    continue
                order = np.argsort(K, kind="stable")
                K = K[order]
                u = sim(h5, l5, o5, c5, K, S[order], E[order], Rk[order], eod[K].astype(np.int64), rr, cost, usd)
                yrs = Y[order]
                m = np.isfinite(u)
                u, yrs = u[m], yrs[m]
                dv, vv = u[yrs < 2023], u[yrs >= 2023]
                pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
                eq = np.cumsum(u)
                rows.append(dict(activo=sym, tf=tf, tam_min=minsz, entrada=entry, stop=stopm, direccion=mode, obj=f"{rr:g}R",
                                 ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2), dev=round(dv.sum() / 5), pf_dev=pf(dv),
                                 val=round(vv.sum() / 3.75), pf_val=pf(vv), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                                 años=f"{sum(u[yrs == y].sum() > 0 for y in range(2018, 2027))}/9"))
            print(sym, tf, len(fv), "FVG", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/fvg_test.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal variantes: {len(R)} · ganan en ambos periodos: {both(R)}")
    print(R.groupby(["activo", "tf", "direccion"]).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g), "acierto medio": round(g.acierto.mean(), 2),
          "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    C = R[(R.dev > 0) & (R.val > 0) & (R.años.str[0].astype(int) >= 7)]
    print(f"\n══ Ganan en ambos periodos y ≥ 7/9 años: {len(C)} ══")
    print(C.sort_values("val", ascending=False).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
