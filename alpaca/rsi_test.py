"""RSI en NQ / MNQ y oro / MGC, intradía, 2018 - oct 2026.

RSI de Wilder sobre el cierre, en velas de 5 min, 15 min o 1 h. Dos versiones:
  RSI 14 · 30/70   la clásica
  RSI 2 · 10/90    la de Larry Connors (muy usada para comprar caídas en índices)
Modos:
  reversión   sobreventa → compra; sobrecompra → venta (lo que se enseña siempre)
  impulso     al revés: sobrecompra → compra; sobreventa → venta (control / seguimiento de tendencia)
Filtro: ninguno · a favor de la EMA 200 de esa temporalidad (solo compras por encima, solo ventas por debajo).
Entrada en la apertura de la vela siguiente a la señal (velas de 5 min). Salida: el RSI cruza 50 (vuelve a la
media), o stop de 0,2 ATR diario, o cierre forzoso 16:00 NY. Señales entre 3:00 y 15:00 NY. Una operación a la vez.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python rsi_test.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m


def rsi(c, n):
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).to_numpy()


@njit(cache=True)
def run(o5, h5, l5, c5, sig_k, sig_s, r_on5, eod, stop_d, cost, usd):
    """sig_k: vela de 5 min de entrada; r_on5: RSI de la temporalidad (último cerrado) visto en cada vela de 5 min."""
    n = len(sig_k)
    out = np.full(n, np.nan)
    busy = -1
    for i in range(n):
        k = sig_k[i]
        if k <= busy or eod[k] <= k:
            continue
        s = sig_s[i]
        e = o5[k]
        sl = e - s * stop_d[i]
        px = c5[eod[k]]
        qe = eod[k]
        for q in range(k, eod[k] + 1):
            if (s == 1 and l5[q] <= sl) or (s == -1 and h5[q] >= sl):
                px = min(sl, o5[q]) if s == 1 else max(sl, o5[q])
                qe = q
                break
            if q > k and ((s == 1 and r_on5[q] >= 50) or (s == -1 and r_on5[q] <= 50)):
                px = c5[q]
                qe = q
                break
        busy = qe
        out[i] = (s * (px - e) - cost) * usd
    return out


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        d5 = load_5m(sym)
        t5 = d5.index
        o5, h5, l5, c5 = (d5[k].to_numpy() for k in ("open", "high", "low", "close"))
        m5 = (t5.hour * 60 + t5.minute).to_numpy()
        gd = (t5 + pd.Timedelta(hours=6)).normalize()
        D = d5.groupby(gd).agg(high=("high", "max"), low=("low", "min"))
        atr5 = (D.high - D.low).rolling(14).mean().shift(1).reindex(gd).to_numpy()
        day5 = np.array(t5.normalize().asi8)
        eod = pd.Series(np.where(m5 < 960, np.arange(len(t5)), -1)).groupby(day5).max().reindex(day5).to_numpy().astype(np.int64)
        for tf, rule, tfm in (("5m", None, 5), ("15m", "15min", 15), ("1h", "60min", 60)):
            b = d5 if rule is None else d5.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            cb = b.close.to_numpy()
            ema = pd.Series(cb).ewm(span=200, adjust=False).mean().to_numpy()
            kk = np.searchsorted(t5.asi8, (b.index + pd.Timedelta(minutes=tfm)).asi8)   # vela de 5 min de entrada
            for (n, lo, hi), mode, filt in itertools.product(((14, 30, 70), (2, 10, 90)), ("reversión", "impulso"), ("ninguno", "EMA 200")):
                r = rsi(cb, n)
                # RSI cerrado visible en cada vela de 5 min
                pos = np.searchsorted(kk, np.arange(len(t5)), side="right") - 1
                r_on5 = np.where(pos >= 0, r[np.maximum(pos, 0)], 50.0)
                cross_dn = (r < lo) & (np.r_[50, r[:-1]] >= lo)
                cross_up = (r > hi) & (np.r_[50, r[:-1]] <= hi)
                side = np.where(cross_dn, 1, np.where(cross_up, -1, 0)) * (1 if mode == "reversión" else -1)
                if mode == "impulso":     # en impulso la salida es cuando el RSI vuelve a 50 en contra: invertimos la lectura
                    r_exit = 100 - r_on5
                else:
                    r_exit = r_on5
                ok = (side != 0) & (kk < len(t5))
                if filt == "EMA 200":
                    ok &= ((side == 1) & (cb > ema)) | ((side == -1) & (cb < ema))
                idx = np.flatnonzero(ok)
                k_ent = kk[idx]
                good = (m5[np.minimum(k_ent, len(t5) - 1)] >= 180) & (m5[np.minimum(k_ent, len(t5) - 1)] <= 900)
                idx, k_ent = idx[good], k_ent[good]
                u = run(o5, h5, l5, c5, k_ent.astype(np.int64), side[idx].astype(np.int64), r_exit, eod,
                        0.2 * atr5[k_ent], cost, usd)
                yrs = t5.year.to_numpy()[k_ent]
                m = np.isfinite(u)
                u, yrs = u[m], yrs[m]
                if len(u) < 80:
                    continue
                dv, vv = u[yrs < 2023], u[yrs >= 2023]
                pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
                eq = np.cumsum(u)
                rows.append(dict(activo=sym, tf=tf, rsi=f"RSI {n} · {lo}/{hi}", modo=mode, filtro=filt, ops_año=round(len(u) / 8.75),
                                 acierto=round((u > 0).mean(), 2), dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vv.sum() / 3.75),
                                 pf_val=pf(vv), peor_racha=round((np.maximum.accumulate(eq) - eq).max()),
                                 años=f"{sum(u[yrs == y].sum() > 0 for y in range(2018, 2027))}/9"))
        print(sym, "listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/rsi_test.pkl")
    both = lambda x: f"{((x.dev > 0) & (x.val > 0)).mean():.0%}"
    print(f"\nTotal variantes: {len(R)} · ganan en ambos periodos: {both(R)}")
    print(R.sort_values(["activo", "modo", "acierto"], ascending=[True, True, False]).to_string(index=False))


if __name__ == "__main__":
    main()
