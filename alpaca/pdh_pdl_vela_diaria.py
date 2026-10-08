"""Estrategia «PDH/PDL + vela diaria + ruptura de estructura en 5 min» (post de sanchezzfx), NQ y oro, 2018 - oct 2026.

1) Velas diarias = sesión Globex (18:00-17:00 NY, como TradingView en futuros). Para operar el día t se miran las
   velas t-1 (ayer) y t-2 (anteayer):
     continuación alcista  ayer CERRÓ por encima del máximo de anteayer             → compras
     liquidity run bajista ayer superó el máximo de anteayer con mecha pero cerró por debajo → ventas hacia el PDL
     continuación bajista  ayer cerró por debajo del mínimo de anteayer             → ventas
     liquidity run alcista ayer perforó el mínimo de anteayer con mecha y cerró por encima  → compras hacia el PDH
   (PDH/PDL de hoy = máximo/mínimo de ayer.)
2) Objetivo: en los liquidity run, el extremo contrario de ayer (PDL para ventas, PDH para compras). En las
   continuaciones, el extremo de ayer en la dirección (PDH para compras, PDL para ventas) o, si ya se superó,
   2R. Variante: 2R fijo en todos los casos.
3) Entrada en 5 min: ruptura de estructura a favor = una vela CIERRA más allá del último máximo (compras) /
   mínimo (ventas) de swing confirmado (fractal de 3 velas). Stop en el último swing contrario. Solo si el
   objetivo está al menos a 1R. Una operación al día. Ventana: NY (9:30-15:30) o Londres+NY (3:00-15:30 NY).
   Cierre forzoso 16:00 NY. Si stop y objetivo caen en la misma vela, cuenta el stop.
Control: la misma entrada por ruptura de estructura pero en la dirección CONTRARIA al sesgo diario, y sin sesgo.
Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC).

Uso:
    python pdh_pdl_vela_diaria.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m


def main():
    pd.set_option("display.width", 250)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        df = load_5m(sym)
        t = df.index
        nm = (t.hour * 60 + t.minute).to_numpy()
        nm = np.where(nm >= 1080, nm - 1440, nm)
        gd = np.array((t + pd.Timedelta(hours=6)).normalize().date)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        groups = pd.Series(np.arange(len(df))).groupby(gd).indices
        keys = sorted(groups)
        D = [(h[groups[k]].max(), l[groups[k]].min(), c[groups[k][-1]]) for k in keys]
        p = 3
        # pivotes confirmados (índice de confirmación = j + p)
        ph = np.full(len(c), np.nan)
        pl = np.full(len(c), np.nan)
        lastH, lastL = np.nan, np.nan
        for i in range(2 * p, len(c)):
            j = i - p
            if h[j] == h[j - p:j + p + 1].max():
                lastH = h[j]
            if l[j] == l[j - p:j + p + 1].min():
                lastL = l[j]
            ph[i], pl[i] = lastH, lastL
        for win, tgt_mode, mode in itertools.product(("NY", "Londres+NY"), ("nivel", "2R"), ("sesgo", "contrario", "sin sesgo")):
            res = []
            for di in range(2, len(keys)):
                (h1, l1, c1), (h2, l2, c2) = D[di - 1], D[di - 2]
                setups = []
                if c1 > h2:
                    setups.append((1, "continuación", h1))
                elif h1 > h2:
                    setups.append((-1, "liquidity run", l1))
                if c1 < l2:
                    setups.append((-1, "continuación", l1))
                elif l1 < l2:
                    setups.append((1, "liquidity run", h1))
                if len(setups) != 1:
                    continue                                    # día interior o señales contradictorias
                bias, kind, lvl = setups[0]
                idx = np.asarray(groups[keys[di]])
                m = nm[idx]
                a = 570 if win == "NY" else 180
                seg = idx[(m >= a) & (m < 960)]
                if len(seg) < 50:
                    continue
                last = seg[-1]
                for j, k in enumerate(seg):
                    if nm[k] > 930:
                        break
                    up = np.isfinite(ph[k - 1]) and c[k] > ph[k - 1] and c[k - 1] <= ph[k - 1]
                    dn = np.isfinite(pl[k - 1]) and c[k] < pl[k - 1] and c[k - 1] >= pl[k - 1]
                    want = bias if mode == "sesgo" else -bias if mode == "contrario" else (1 if up else -1 if dn else 0)
                    if not ((want == 1 and up) or (want == -1 and dn)):
                        continue
                    s, e = want, c[k]
                    sl = pl[k] if s == 1 else ph[k]
                    if not np.isfinite(sl) or (s == 1 and sl >= e) or (s == -1 and sl <= e):
                        continue
                    risk = abs(e - sl)
                    if tgt_mode == "2R" or mode != "sesgo":
                        tg = e + s * 2 * risk
                    else:
                        tg = lvl if s * (lvl - e) >= risk else (e + s * 2 * risk if kind == "continuación" else None)
                        if tg is None:
                            continue
                    px = c[last]
                    for q in seg[j + 1:]:
                        if (s == 1 and l[q] <= sl) or (s == -1 and h[q] >= sl):
                            px = min(sl, o[q]) if s == 1 else max(sl, o[q])
                            break
                        if (s == 1 and h[q] >= tg) or (s == -1 and l[q] <= tg):
                            px = tg
                            break
                    res.append((pd.Timestamp(keys[di]).year, kind, (s * (px - e) - cost) * usd, (s * (px - e)) / risk, px == tg))
                    break
            R = pd.DataFrame(res, columns=["y", "tipo", "u", "R", "obj"])
            for kind, g in [("todo", R)] + list(R.groupby("tipo")):
                if len(g) < 40:
                    continue
                d, v = g[g.y < 2023].u, g[g.y >= 2023].u
                pf = lambda z: round(z[z > 0].sum() / -z[z < 0].sum(), 2)
                eq = g.u.cumsum()
                rows.append(dict(activo=sym, ventana=win, objetivo=tgt_mode, direccion=mode, setup=kind, ops_año=round(len(g) / 8.75),
                                 acierto=round((g.u > 0).mean(), 2), llega_obj=round(g.obj.mean(), 2), R_medio=round(g.R.mean(), 2),
                                 dev=round(d.sum() / 5), pf_dev=pf(d), val=round(v.sum() / 3.75), pf_val=pf(v),
                                 peor_racha=round((eq.cummax() - eq).max()), años=f"{(g.groupby('y').u.sum() > 0).sum()}/9"))
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/pdh_pdl_vela_diaria.pkl")
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
