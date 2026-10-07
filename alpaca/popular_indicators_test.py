"""Indicadores de señales más conocidos de TradingView, probados en NQ / MNQ con el mismo método de siempre.

Réplicas de las versiones públicas más usadas (parámetros por defecto):
  Supertrend (10, 3)          ATR de Wilder, bandas sobre hl2
  UT Bot Alerts (1, 10)       stop dinámico de ATR sobre el cierre
  Chandelier Exit (22, 3)     máximo/mínimo de 22 ± 3 ATR, cambio de dirección al cruzar
  Parabolic SAR (0,02 / 0,2)
  MACD (12, 26, 9)            MACD por encima / debajo de su señal
  Squeeze Momentum (LazyBear) signo del momento (regresión lineal de 20)
Operativa: señal al cierre de la vela del indicador, entrada a la apertura siguiente, salida con la señal
contraria (o cierre a las 16:00 NY). Variantes: temporalidad 5 / 15 min / 1 h; ventana NY (9:30-15:30 entradas)
o Globex (cerrado antes de las 17:00); ambos lados o solo largos; solo cambios nuevos o también el estado al
abrir. Datos NQ 5 min 2018 - oct 2026. Se ELIGE con 2018-2022 y se JUZGA con 2023-2026. Coste 1 punto; 1 MNQ.
Control: ES con las mismas reglas.

Uso:
    python popular_indicators_test.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

import ema_cross_research as E
from crt_backtest import load_5m


def wilder_atr(b, n):
    pc = b.close.shift()
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    return tr.ewm(alpha=1 / n, adjust=False).mean()


@njit(cache=True)
def st_rec(c, up0, dn0):
    n = len(c)
    up, dn, d = up0.copy(), dn0.copy(), np.ones(n)
    for i in range(1, n):
        up[i] = max(up0[i], up[i - 1]) if c[i - 1] > up[i - 1] else up0[i]
        dn[i] = min(dn0[i], dn[i - 1]) if c[i - 1] < dn[i - 1] else dn0[i]
        if d[i - 1] == -1 and c[i] > dn[i - 1]:
            d[i] = 1
        elif d[i - 1] == 1 and c[i] < up[i - 1]:
            d[i] = -1
        else:
            d[i] = d[i - 1]
    return d


@njit(cache=True)
def ut_rec(c, nloss):
    n = len(c)
    ts = np.zeros(n)
    d = np.zeros(n)
    ts[0] = c[0]
    for i in range(1, n):
        if c[i] > ts[i - 1] and c[i - 1] > ts[i - 1]:
            ts[i] = max(ts[i - 1], c[i] - nloss[i])
        elif c[i] < ts[i - 1] and c[i - 1] < ts[i - 1]:
            ts[i] = min(ts[i - 1], c[i] + nloss[i])
        elif c[i] > ts[i - 1]:
            ts[i] = c[i] - nloss[i]
        else:
            ts[i] = c[i] + nloss[i]
        d[i] = 1 if c[i] > ts[i] else -1
    return d


@njit(cache=True)
def ce_rec(c, ls0, ss0):
    n = len(c)
    ls, ss, d = ls0.copy(), ss0.copy(), np.ones(n)
    for i in range(1, n):
        ls[i] = max(ls0[i], ls[i - 1]) if c[i - 1] > ls[i - 1] else ls0[i]
        ss[i] = min(ss0[i], ss[i - 1]) if c[i - 1] < ss[i - 1] else ss0[i]
        d[i] = 1 if c[i] > ss[i - 1] else -1 if c[i] < ls[i - 1] else d[i - 1]
    return d


@njit(cache=True)
def psar_rec(h, l, start, inc, mx):
    n = len(h)
    d = np.ones(n)
    sar = l[0]
    ep = h[0]
    af = start
    up = True
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < sar:
                up, sar, ep, af = False, ep, l[i], start
            elif h[i] > ep:
                ep, af = h[i], min(af + inc, mx)
        else:
            sar = max(sar, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > sar:
                up, sar, ep, af = True, ep, h[i], start
            elif l[i] < ep:
                ep, af = l[i], min(af + inc, mx)
        d[i] = 1 if up else -1
    return d


def linreg_last(y, n):
    x = np.arange(n)
    xm = x.mean()
    w = (x - xm) / ((x - xm) ** 2).sum()
    slope = y.rolling(n).apply(lambda v: (w * v).sum(), raw=True)
    mean = y.rolling(n).mean()
    return mean + slope * (n - 1 - xm)


def directions(b):
    c, h, l = b.close.to_numpy(), b.high.to_numpy(), b.low.to_numpy()
    out = {}
    a10 = wilder_atr(b, 10).to_numpy()
    hl2 = ((b.high + b.low) / 2).to_numpy()
    out["Supertrend (10, 3)"] = st_rec(c, hl2 - 3 * a10, hl2 + 3 * a10)
    out["UT Bot (1, 10)"] = ut_rec(c, 1 * a10)
    a22 = wilder_atr(b, 22).to_numpy()
    out["Chandelier Exit (22, 3)"] = ce_rec(c, b.high.rolling(22).max().to_numpy() - 3 * a22, b.low.rolling(22).min().to_numpy() + 3 * a22)
    out["Parabolic SAR"] = psar_rec(h, l, 0.02, 0.02, 0.2)
    m = b.close.ewm(span=12, adjust=False).mean() - b.close.ewm(span=26, adjust=False).mean()
    out["MACD (12, 26, 9)"] = np.sign(m - m.ewm(span=9, adjust=False).mean()).to_numpy()
    mid = ((b.high.rolling(20).max() + b.low.rolling(20).min()) / 2 + b.close.rolling(20).mean()) / 2
    out["Squeeze Momentum"] = np.sign(linreg_last(b.close - mid, 20)).fillna(0).to_numpy()
    return out


def run(sym):
    df = load_5m(sym)
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    wins = {"NY": ((hm >= 570) & (hm < 960), (hm >= 570) & (hm <= 930), hm == 955),
            "Globex": ((hm >= 1080) | (hm < 1020), (hm >= 1080) | (hm < 960), hm == 1015)}
    to_year = lambda dd: dd.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for tfn, tf in (("5m", 5), ("15m", 15), ("1h", 60)):
        b = E.tf_frame(df, tf)
        dirs = directions(b)
        for k, v in dirs.items():
            b[k] = v
        A = E.align(df, b, list(dirs))
        for name, (wn, (win, can, last)), lo, fr in itertools.product(dirs, wins.items(), (0, 1), (1, 0)):
            idx = np.flatnonzero(win)
            st = np.nan_to_num(A[name])[idx]
            pnl, dd = E.sim(o[idx], h[idx], l[idx], c[idx], st, np.zeros(len(idx)), np.zeros(len(idx)),
                            np.where(win, gday, -1)[idx], can[idx], last[idx], lo, 0, 0.0, fr, 1.0)
            if len(pnl) < 50:
                continue
            y = to_year(dd)
            u = pnl * 2
            r = dict(indicador=name, tf=tfn, ventana=wn, lado="largos" if lo else "ambos", entrada="cambio" if fr else "estado")
            for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
                vv = u[sel]
                g, ls = vv[vv > 0].sum(), -vv[vv < 0].sum()
                r |= {f"{nm_}_ops": round(len(vv) / yrs), f"{nm_}_usd": round(vv.sum() / yrs), f"{nm_}_pf": round(g / ls, 2) if ls else np.inf}
            eq = np.cumsum(u)
            r["dd"] = round((np.maximum.accumulate(eq) - eq).max())
            r["años"] = f"{(pd.Series(u).groupby(y).sum() > 0).sum()}/{len(set(y))}"
            r["acierto"] = round((u > 0).mean(), 2)
            rows.append(r)
        print(f"{sym} {tfn} listo", flush=True)
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250)
    both = lambda x: f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}"
    for sym in ("NQ", "ES"):
        R = run(sym)
        R.to_pickle(f".lab_cache/popular_{sym}.pkl")
        print(f"\n══════ {sym}: {len(R)} variantes · ganan en ambos periodos: {both(R)} ══════")
        print(R.groupby(["indicador", "tf"]).apply(lambda x: pd.Series({"% ambos": both(x), "med dev $": int(x.dev_usd.median()),
              "med val $": int(x.val_usd.median()), "med PF val": x.val_pf.median(), "acierto": x.acierto.median()}),
              include_groups=False).unstack("tf").to_string())
        if sym == "NQ":
            print("\nMejores (peor periodo más alto), NQ:")
            S = R.assign(mn=R[["dev_usd", "val_usd"]].min(axis=1)).sort_values("mn", ascending=False)
            print(S.head(15).drop(columns="mn").to_string(index=False))


if __name__ == "__main__":
    main()
