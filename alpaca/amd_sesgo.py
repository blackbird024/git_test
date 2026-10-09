"""Patrón AMD / Power of 3 (acumulación · manipulación · distribución) con y sin sesgo. NQ / MNQ y oro / MGC, 2018 - oct 2026.

Regla mecánica habitual (ICT): referencia = apertura de medianoche NY (00:00).
  Alcista: a la hora T el precio está POR ENCIMA de la apertura de medianoche y el mínimo del día (desde 00:00) se hizo
           POR DEBAJO de ella (la «manipulación» barrió hacia abajo) → compra a la hora T, stop 1 tick bajo ese mínimo.
  Bajista: espejo (máximo del día por encima de la apertura y precio por debajo) → venta, stop sobre ese máximo.
  (Si se cumplen las dos, no se opera.)
Hora T: 9:30 · 10:00 NY (NQ) — oro también 8:30 NY (apertura COMEX). Objetivo 2R · 3R · cierre 16:00 NY.
Sesgo: ninguno · RSI 14 de 1 h EN CONTRA (el filtro del rango de ayer: RSI > 50 → solo ventas) · RSI A FAVOR.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python amd_sesgo.py
"""

import itertools

import numpy as np
import pandas as pd

import mezcla_filtros as M
from crt_backtest import load_5m


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd, tick, times in (("NQ", 1.0, 2.0, 0.25, (570, 600)), ("GC", 0.3, 10.0, 0.1, (510, 570, 600))):
        df = load_5m(sym)
        t = df.index
        hm = (t.hour * 60 + t.minute).to_numpy()
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        rsi = M.context(df)["RSI 1h"]
        groups = pd.Series(np.arange(len(df))).groupby(np.array(t.normalize().asi8)).indices
        for T, bias_mode, rr in itertools.product(times, ("sin sesgo", "RSI en contra", "RSI a favor"), (2.0, 3.0, 0.0)):
            res = []
            for d in sorted(groups):
                idx = np.asarray(groups[d])
                m = hm[idx]
                pre = idx[m < T]
                at = idx[m == T]
                sess = idx[(m >= T) & (m < 960)]
                if len(pre) < (T // 5) * 0.8 or len(at) == 0 or len(sess) < 20:
                    continue
                O0 = o[pre[0]]
                H0, L0 = h[pre].max(), l[pre].min()
                px0 = o[at[0]]
                up = L0 < O0 < px0
                dn = H0 > O0 > px0
                if up == dn:
                    continue
                s = 1 if up else -1
                if bias_mode != "sin sesgo" and np.isfinite(rsi[at[0]]):
                    b = -int(rsi[at[0]])
                    if bias_mode == "RSI a favor":
                        b = -b
                    if b != s:
                        continue
                e = px0
                sl = L0 - tick if s == 1 else H0 + tick
                risk = s * (e - sl)
                if risk <= 0:
                    continue
                tg = e + s * rr * risk if rr else None
                px = c[sess[-1]]
                for q in sess:
                    if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                        px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                        break
                    if tg is not None and ((s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg)):
                        px = tg
                        break
                res.append((t[at[0]].year, (s * (px - e) - cost) * usd, risk * usd))
            R = pd.DataFrame(res, columns=["y", "u", "riesgo"])
            if len(R) < 50:
                continue
            dv, vv = R[R.y < 2023].u, R[R.y >= 2023].u
            pf = lambda z: round(z[z > 0].sum() / max(-z[z < 0].sum(), 1e-9), 2)
            eq = R.u.cumsum()
            rows.append(dict(activo=sym, hora=f"{T // 60}:{T % 60:02d}", sesgo=bias_mode, obj=f"{rr:g}R" if rr else "cierre",
                             ops_año=round(len(R) / 8.75), acierto=f"{(R.u > 0).mean():.0%}", riesgo_med=int(R.riesgo.median()),
                             dev=round(dv.sum() / 5), pf_dev=pf(dv), val=round(vv.sum() / 3.75), pf_val=pf(vv),
                             peor_racha=round((eq.cummax() - eq).max()), años=f"{(R.groupby('y').u.sum() > 0).sum()}/9"))
        print(sym, "listo", flush=True)
    T_ = pd.DataFrame(rows)
    T_.to_pickle(".lab_cache/amd_sesgo.pkl")
    print(T_.to_string(index=False))


if __name__ == "__main__":
    main()
