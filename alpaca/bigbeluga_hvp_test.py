"""Prueba del indicador «High Volume Pivot Support & Resistance Zones [BigBeluga]» en NQ / MNQ.

Réplica de su lógica (Pine v6), vela a vela y solo con información ya conocida:
  · Pivote de máximo/mínimo de 40 velas a cada lado (se confirma 40 velas DESPUÉS) con volumen de la vela del
    pivote > 1,2 × media de 20 → nueva zona (solo cuenta la última de cada tipo).
  · Resistencia: del máximo del cuerpo del pivote hasta + ATR(200). Soporte: del mínimo del cuerpo hasta − ATR(200).
  · Señales (al cierre de la vela; el indicador las dibuja desplazadas una vela atrás con offset = -1):
      Res Breakout        primer cierre por encima de la resistencia        → largo
      Sup Breakdown       primer cierre por debajo del soporte              → corto
      Resistance retest   máximo anterior tocó la base de la resistencia y el actual queda por debajo → corto
      Support retest      mínimo anterior tocó el techo del soporte y el actual queda por encima      → largo
      Flipped Res retest  resistencia rota: el precio vuelve a su techo y rebota hacia arriba       → largo
      Flipped Sup retest  soporte roto: el precio vuelve a su base y rebota hacia abajo             → corto
Operación: entrada a la apertura de la vela siguiente; stop a 1 ATR(200) (el alto de la zona); objetivo 1R o 2R;
salida máxima a las 24 velas o, en la versión NY, a las 16:00. Coste 1 punto; 1 MNQ (2 $/punto).
Datos: NQ 1 min con volumen (Databento) 2018 - oct 2026 agrupado en 5 y 15 min.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026.

Uso:
    python bigbeluga_hvp_test.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

SIGS = ["Res Breakout (L)", "Sup Breakdown (C)", "Resistance retest (C)", "Support retest (L)", "Flipped Res retest (L)", "Flipped Sup retest (C)"]
SIDE = np.array([1, -1, -1, 1, 1, -1])


@njit(cache=True)
def signals(o, h, l, c, v, atr, vavg, L, vmult):
    n = len(c)
    out = np.zeros((n, 6), np.bool_)
    rT, rB, sT, sB = np.nan, np.nan, np.nan, np.nan
    rBroken, sBroken = False, False
    rBreakBar, sBreakBar = -10, -10
    for i in range(2 * L + 1, n):
        j = i - L
        # pivote de máximo confirmado en i (vela j es la mayor de j-L .. j+L)
        isph = True
        ispl = True
        for k in range(j - L, j + L + 1):
            if k == j:
                continue
            if k < j and h[k] >= h[j]:
                isph = False
            if k > j and h[k] > h[j]:
                isph = False
            if k < j and l[k] <= l[j]:
                ispl = False
            if k > j and l[k] < l[j]:
                ispl = False
        hv = v[j] > vavg[j] * vmult
        if isph and hv:
            rB = max(o[j], c[j])
            rT = rB + atr[j]
            rBroken = False
        elif rT == rT:
            if c[i] < rT:
                if h[i - 1] >= rB and h[i] < rB:
                    out[i, 2] = True
            if c[i] > rT:
                if not rBroken:
                    out[i, 0] = True
                    rBroken = True
                    rBreakBar = i
                if l[i - 1] <= rT and l[i] > rT and i - rBreakBar > 1:
                    out[i, 4] = True
        if ispl and hv:
            sT = min(o[j], c[j])
            sB = sT - atr[j]
            sBroken = False
        elif sB == sB:
            if c[i] < sB:
                if not sBroken:
                    out[i, 1] = True
                    sBroken = True
                    sBreakBar = i
                if h[i - 1] >= sB and h[i] < sB:
                    out[i, 5] = True
            if c[i] > sB:
                if l[i - 1] <= sT and l[i] > sT:
                    out[i, 3] = True
    return out


@njit(cache=True)
def trade(o, h, l, c, atr, sig, side, okent, xbar, rr, maxbars, cost):
    n = len(c)
    pnl = np.empty(n)
    idx = np.empty(n, np.int64)
    nt = 0
    busy = -1
    for i in range(n - 2):
        if not sig[i] or not okent[i] or i <= busy:
            continue
        e = o[i + 1]
        risk = atr[i]
        sl = e - side * risk
        tg = e + side * rr * risk
        end = min(i + maxbars, xbar[i]) if xbar[i] > i else i + maxbars
        end = min(end, n - 1)
        res = np.nan
        for q in range(i + 1, end + 1):
            if (side == 1 and l[q] <= sl) or (side == -1 and h[q] >= sl):
                res = side * ((min(sl, o[q]) if side == 1 else max(sl, o[q])) - e)
                break
            if (side == 1 and h[q] >= tg) or (side == -1 and l[q] <= tg):
                res = rr * risk
                break
        if res != res:
            res = side * (c[end] - e)
            q = end
        pnl[nt] = res - cost
        idx[nt] = i
        nt += 1
        busy = q
    return pnl[:nt], idx[:nt]


def main():
    from vwap_globex_8y import load
    pd.set_option("display.width", 250)
    d1 = load()[["open", "high", "low", "close", "volume"]].sort_index()
    d1.index = d1.index.tz_convert("America/New_York")
    rows = []
    for tf in (5, 15):
        b = d1.resample(f"{tf}min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
        v = b.volume.to_numpy().astype(float)
        pc = np.r_[c[0], c[:-1]]
        tr = pd.Series(np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc))))
        atr = tr.ewm(alpha=1 / 200, adjust=False).mean().to_numpy()
        vavg = pd.Series(v).rolling(20).mean().to_numpy()
        t = b.index
        hm = (t.hour * 60 + t.minute).to_numpy()
        years = t.year.to_numpy()
        gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
        # índice de la última vela de la sesión de NY del mismo día (para cerrar a las 16:00)
        lastny = pd.Series(np.where(hm == 960 - tf, np.arange(len(c)), -1)).groupby(gday).transform("max").to_numpy()
        for L in (40, 20):
            S = signals(o, h, l, c, v, atr, np.nan_to_num(vavg, nan=1e18), L, 1.2)
            for k, name in enumerate(SIGS):
                for ses, rr in itertools.product(("24 h", "NY 9:30-15:30"), (1.0, 2.0)):
                    if ses == "24 h":
                        ok = np.ones(len(c), bool)
                        xb = np.full(len(c), -1)
                    else:
                        ok = (hm >= 570) & (hm <= 930)
                        xb = lastny
                    pnl, ix = trade(o, h, l, c, atr, S[:, k], int(SIDE[k]), ok, xb, rr, 24, 1.0)
                    if len(pnl) < 30:
                        continue
                    y = years[ix]
                    u = pnl * 2
                    r = dict(tf=f"{tf}m", pivote=L, señal=name, sesion=ses, obj=f"{rr:g}R")
                    for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
                        vv = u[sel]
                        g, ls = vv[vv > 0].sum(), -vv[vv < 0].sum()
                        r |= {f"{nm_}_ops": round(len(vv) / yrs), f"{nm_}_win": round((vv > 0).mean(), 2),
                              f"{nm_}_usd": round(vv.sum() / yrs), f"{nm_}_pf": round(g / ls, 2) if ls else np.inf}
                    eq = np.cumsum(u)
                    r["dd"] = round((np.maximum.accumulate(eq) - eq).max())
                    r["años"] = f"{(pd.Series(u).groupby(y).sum() > 0).sum()}/{len(set(y))}"
                    rows.append(r)
        print(f"{tf}m listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/bigbeluga_hvp.pkl")
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    print(f"\n{len(R)} variantes · ganan en ambos periodos: {both(R)}")
    print(R.groupby("señal").apply(lambda x: pd.Series({"n": len(x), "% ambos": both(x), "acierto med": x.val_win.median(),
          "med dev $": int(x.dev_usd.median()), "med val $": int(x.val_usd.median()), "ops/año": int(x.val_ops.median())}),
          include_groups=False).to_string())
    print("\nDetalle (pivote 40, el valor por defecto):")
    print(R[R.pivote == 40].to_string(index=False))


if __name__ == "__main__":
    main()
