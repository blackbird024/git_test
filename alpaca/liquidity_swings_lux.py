"""Liquidity Swings [LuxAlgo] reproducido y convertido en estrategias. NQ / MNQ y oro / MGC, 2018 - oct 2026.

El indicador (descripción pública de LuxAlgo):
  · Pivote alto / bajo con «Pivot Lookback» (14 por defecto) velas a cada lado (se confirma 14 velas después).
  · Zona «Wick Extremity»: del máximo al cuerpo de la vela pivote (máx(apertura, cierre)); en mínimos, del mínimo al
    mín(apertura, cierre). Solo está viva la zona del último pivote de cada lado.
  · Cuenta las velas que vuelven a entrar en la zona (y su volumen) y la zona se da por cruzada cuando una vela CIERRA
    más allá de ella (por encima del máximo de una zona alta / por debajo del mínimo de una zona baja).
Estrategias (zona alta; la baja es el espejo), evaluadas al cierre de la vela de la temporalidad:
  barrida   la vela supera el máximo de la zona con la mecha pero cierra por debajo → VENTA (toma de liquidez)
            stop: máximo de esa vela
  ruptura   la vela cierra por encima de la zona (la zona se cruza) → COMPRA; stop: mínimo de la zona (cuerpo)
  rechazo   la vela entra en la zona sin superar su máximo y cierra por debajo de ella → VENTA; stop: máximo de la zona
Filtro de «toques» (lo que muestra el indicador): todas · zonas con ≥ 3 toques previos.
Temporalidad 5 min, 15 min, 1 h; lookback 14 (y 5 en 1 h). Entrada en la apertura de la siguiente vela de 5 min;
objetivo 1R · 2R · cierre; cierre forzoso 16:00 NY; señales 3:00-15:00 NY. Una operación a la vez.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python liquidity_swings_lux.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m
from soportes_trendlines import sim


@njit(cache=True)
def events(o, h, l, c, L):
    """Devuelve arrays (i, tipo, lado, stop, toques): tipo 0 barrida, 1 ruptura, 2 rechazo."""
    n = len(c)
    cap = 2 * n
    oi = np.empty(cap, np.int64); ot = np.empty(cap, np.int64); os_ = np.empty(cap, np.int64)
    osl = np.empty(cap, np.float64); on = np.empty(cap, np.int64)
    m = 0
    ph_top = ph_btm = pl_top = pl_btm = np.nan
    ph_cnt = pl_cnt = 0
    ph_alive = pl_alive = False
    for i in range(2 * L, n):
        j = i - L
        # nuevo pivote alto / bajo confirmado en la vela i
        is_ph = True
        is_pl = True
        for k in range(j - L, j + L + 1):
            if h[k] > h[j]:
                is_ph = False
            if l[k] < l[j]:
                is_pl = False
        if is_ph:
            ph_top, ph_btm, ph_alive, ph_cnt = h[j], max(o[j], c[j]), True, 0
            for k in range(j + 1, i):
                if h[k] > ph_btm and l[k] < ph_top:
                    ph_cnt += 1
        if is_pl:
            pl_top, pl_btm, pl_alive, pl_cnt = min(o[j], c[j]), l[j], True, 0
            for k in range(j + 1, i):
                if l[k] < pl_top and h[k] > pl_btm:
                    pl_cnt += 1
        if ph_alive and not is_ph and ph_top > ph_btm:
            if c[i] > ph_top:
                oi[m] = i; ot[m] = 1; os_[m] = 1; osl[m] = ph_btm; on[m] = ph_cnt; m += 1
                ph_alive = False
            elif h[i] > ph_top:
                oi[m] = i; ot[m] = 0; os_[m] = -1; osl[m] = h[i]; on[m] = ph_cnt; m += 1
                ph_cnt += 1
            elif h[i] > ph_btm and c[i] < ph_btm:
                oi[m] = i; ot[m] = 2; os_[m] = -1; osl[m] = ph_top; on[m] = ph_cnt; m += 1
                ph_cnt += 1
            elif h[i] > ph_btm:
                ph_cnt += 1
        if pl_alive and not is_pl and pl_top > pl_btm:
            if c[i] < pl_btm:
                oi[m] = i; ot[m] = 1; os_[m] = -1; osl[m] = pl_top; on[m] = pl_cnt; m += 1
                pl_alive = False
            elif l[i] < pl_btm:
                oi[m] = i; ot[m] = 0; os_[m] = 1; osl[m] = l[i]; on[m] = pl_cnt; m += 1
                pl_cnt += 1
            elif l[i] < pl_top and c[i] > pl_top:
                oi[m] = i; ot[m] = 2; os_[m] = 1; osl[m] = pl_btm; on[m] = pl_cnt; m += 1
                pl_cnt += 1
            elif l[i] < pl_top:
                pl_cnt += 1
    return oi[:m], ot[:m], os_[:m], osl[:m], on[:m]


def main():
    pd.set_option("display.width", 250)
    rows = []
    TIPOS = ["barrida", "ruptura", "rechazo"]
    for sym, cost, usd, tick in (("NQ", 1.0, 2.0, 0.25), ("GC", 0.3, 10.0, 0.1)):
        d5 = load_5m(sym)
        t5 = d5.index
        o5, h5, l5, c5 = (d5[k].to_numpy() for k in ("open", "high", "low", "close"))
        m5 = (t5.hour * 60 + t5.minute).to_numpy()
        day5 = np.array(t5.normalize().asi8)
        eod = pd.Series(np.where(m5 < 960, np.arange(len(t5)), -1)).groupby(day5).max().reindex(day5).to_numpy().astype(np.int64)
        yr5 = t5.year.to_numpy()
        for tf, rule, tfm, L in (("5m", None, 5, 14), ("15m", "15min", 15, 14), ("1h", "60min", 60, 14), ("1h", "60min", 60, 5)):
            b = d5 if rule is None else d5.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            I, Ty, S, SL, N = events(*(b[k].to_numpy() for k in ("open", "high", "low", "close")), L)
            ke = np.searchsorted(t5.asi8, (b.index[I] + pd.Timedelta(minutes=tfm)).asi8)
            ok = ke < len(t5)
            I, Ty, S, SL, N, ke = I[ok], Ty[ok], S[ok], SL[ok], N[ok], ke[ok]
            mm = m5[ke]
            ok = (mm >= 180) & (mm <= 900) & (eod[ke] > ke)
            I, Ty, S, SL, N, ke = I[ok], Ty[ok], S[ok], SL[ok], N[ok], ke[ok]
            e = o5[ke]
            SL = SL + S * -tick                         # 1 tick más allá
            risk = S * (e - SL)
            for tipo, minc, rr in itertools.product(range(3), (0, 3), (1.0, 2.0, 0.0)):
                sel = (Ty == tipo) & (N >= minc) & (risk > 0)
                if sel.sum() < 80:
                    continue
                u = sim(h5, l5, o5, c5, ke[sel].astype(np.int64), S[sel].astype(np.int64), e[sel], risk[sel], eod[ke[sel]],
                        rr if rr else 1e6, cost, usd)
                yrs = yr5[ke[sel]]
                m = np.isfinite(u)
                u, yrs = u[m], yrs[m]
                dv, vv = u[yrs < 2023], u[yrs >= 2023]
                pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
                eq = np.cumsum(u)
                rows.append(dict(activo=sym, tf=tf, lookback=L, estrategia=TIPOS[tipo], toques="≥ 3" if minc else "todas",
                                 obj=f"{rr:g}R" if rr else "cierre", ops_año=round(len(u) / 8.75), acierto=round((u > 0).mean(), 2),
                                 dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vv.sum() / 3.75), pf_val=pf(vv),
                                 peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                                 años=f"{sum(u[yrs == y].sum() > 0 for y in range(2018, 2027))}/9"))
            print(sym, tf, L, "eventos", len(I), flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/liquidity_swings_lux.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal variantes: {len(R)} · ganan en ambos periodos: {both(R)}")
    print(R.groupby(["activo", "estrategia"]).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g), "acierto medio": round(g.acierto.mean(), 2),
          "med dev": int(g.dev.median()), "med val": int(g.val.median())}), include_groups=False).to_string())
    C = R[(R.dev > 0) & (R.val > 0)]
    print(f"\n══ Ganan en ambos periodos ({len(C)}) ══")
    print(C.sort_values("val", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
