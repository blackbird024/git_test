"""Prueba de los dos métodos concretos de la masterclass «Life in Trading» (David, World Cup de day trading).

A) SWING CON MEDIAS SIMPLES 6 / 70 / 200 (gráfico diario, solo largos)
   Condiciones: SMA 200 con pendiente positiva, SMA 70 por encima de la 200 y con pendiente positiva.
   Entrada: la SMA 6 cruza al alza la SMA 70.  Salida: la SMA 6 cruza a la baja la SMA 70.
   (Pendiente positiva = la media hoy está por encima de la de hace 10 sesiones.) Entrada y salida a la apertura
   siguiente; coste 0,05 % por lado. Se compara con: el mismo cruce sin condiciones y con comprar y mantener.
   Universo: 99 acciones grandes de EE. UU. (2016-2026, ajustadas), ETF QQQ/SPY/IWM/DIA/GLD y futuros NQ/ES/GC.

B) DIVERGENCIA + RETROCESO AL 66 % (intradía)
   Dos mínimos seguidos (fractales de 3 velas), el segundo más bajo que el primero; divergencia si en el segundo
   el VOLUMEN es menor o el ESTOCÁSTICO (14, 3, 5; %K) es mayor. Se traza el retroceso desde el máximo absoluto
   entre los dos mínimos hasta el segundo mínimo; objetivo en el 50 %, 61,8 % o 66 % de ese tramo. Espejo para
   máximos (cortos). Entrada al confirmarse el segundo mínimo (cierre de la vela), stop un poco más allá del
   mínimo, cierre forzoso a fin de sesión. Se compara con los mismos dobles mínimos SIN divergencia (control).
   NQ (velas de 5 y 1 min con volumen, sesión de NY) y oro (5 min, 3:00-13:30 NY, solo estocástico: sin volumen).
   Coste NQ 1 punto (2 $/punto por MNQ) · oro 0,3 puntos (10 $/punto por MGC). 2018 - oct 2026.

Uso:
    python masterclass_test.py
"""

import pickle

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

CACHE = ".lab_cache"


# ═════════════════════════════════ A) swing 6/70/200 ═════════════════════════════════

def swing(df, cost=0.0005, filtered=True):
    c, o = df.close, df.open
    s6, s70, s200 = c.rolling(6).mean(), c.rolling(70).mean(), c.rolling(200).mean()
    ok = (s200 > s200.shift(10)) & (s70 > s200) & (s70 > s70.shift(10)) if filtered else pd.Series(True, index=c.index)
    up = (s6 > s70) & (s6.shift() <= s70.shift())
    dn = (s6 < s70) & (s6.shift() >= s70.shift())
    oo, n = o.to_numpy(), len(c)
    ent, exi = (up & ok).to_numpy(), dn.to_numpy()
    pos, e, trades, inmkt = 0, 0.0, [], np.zeros(n, bool)
    eq = np.ones(n)
    cc = c.to_numpy()
    for i in range(n - 1):
        if pos:
            inmkt[i] = True
        if pos and exi[i]:
            trades.append(oo[i + 1] / e * (1 - cost) ** 2 - 1)
            pos = 0
        elif not pos and ent[i] and np.isfinite(s200.iat[i]):
            pos, e = 1, oo[i + 1]
    if pos:
        trades.append(cc[-1] / e * (1 - cost) ** 2 - 1)
    r = c.pct_change().fillna(0).to_numpy()
    strat = np.where(np.r_[False, inmkt[:-1]], r, 0.0)
    eq = np.cumprod(1 + strat)
    yrs = (c.index[-1] - c.index[200]).days / 365.25
    bh = cc[-1] / cc[200] - 1
    st = eq[-1] / eq[200] - 1
    dd = (1 - eq / np.maximum.accumulate(eq)).max()
    bheq = cc / np.maximum.accumulate(cc)
    sh = strat[200:].mean() / strat[200:].std() * np.sqrt(252) if strat[200:].std() else 0
    rb = r[200:]
    return dict(ops=len(trades), acierto=np.mean([t > 0 for t in trades]) if trades else np.nan,
                media_op=np.mean(trades) if trades else np.nan, tiempo_dentro=inmkt[200:].mean(),
                cagr=(1 + st) ** (1 / yrs) - 1, cagr_bh=(1 + bh) ** (1 / yrs) - 1, dd=dd, dd_bh=(1 - bheq[200:]).max(),
                sharpe=sh, sharpe_bh=rb.mean() / rb.std() * np.sqrt(252))


SECTOR = {**{s: "tecnología" for s in "AAPL MSFT NVDA AVGO ORCL AMD INTC CSCO ADBE CRM QCOM TXN IBM MU AMAT".split()},
          **{s: "comunicación" for s in "GOOGL META NFLX DIS T VZ CMCSA TMUS CHTR".split()},
          **{s: "financiero" for s in "JPM BAC WFC GS MS C V MA AXP BLK".split()},
          **{s: "energía" for s in "XOM CVX COP SLB EOG OXY PSX MPC VLO HAL".split()},
          **{s: "salud" for s in "JNJ PFE MRK ABBV LLY UNH TMO ABT DHR BMY".split()},
          **{s: "consumo" for s in "KO PEP PG WMT COST HD MCD NKE SBUX LOW TGT AMZN TSLA".split()},
          **{s: "industria" for s in "CAT DE HON GE BA LMT RTX UPS UNP MMM".split()},
          **{s: "utilities" for s in "NEE DUK SO D AEP EXC SRE XEL".split()},
          **{s: "materiales" for s in "LIN APD SHW FCX NEM ECL BALL DD".split()},
          **{s: "inmobiliario" for s in "PLD AMT CCI SPG EQIX O".split()}}


def part_a():
    data = {}
    b = pickle.load(open(f"{CACHE}/sp_daily_basket.pkl", "rb"))
    for s, g in b.groupby(level=0):
        g = g.droplevel(0)
        g.index = pd.to_datetime(g.index).tz_convert(None).normalize()
        data[s] = g[["open", "high", "low", "close"]]
    for s in ("QQQ", "SPY", "IWM", "DIA", "GLD"):
        f = "QQQ_daily_20261004.pkl" if s == "QQQ" else "GLD_daily_20261004.pkl" if s == "GLD" else f"{s}_daily_20261001.pkl"
        g = pickle.load(open(f"{CACHE}/{f}", "rb"))
        g.index = pd.to_datetime(g.index)
        data[s] = g
    for s in ("NQ", "ES", "GC"):
        d = load_5m(s)
        k = (d.index + pd.Timedelta(hours=6)).normalize()
        data[s + " (futuro)"] = d.groupby(k).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    rows = []
    for s, df in data.items():
        if len(df) < 400:
            continue
        a, n = swing(df, filtered=True), swing(df, filtered=False)
        rows.append(dict(simbolo=s, sector=SECTOR.get(s, "índice/ETF/futuro"), **{k: a[k] for k in a},
                         cagr_sin_filtro=n["cagr"], sharpe_sin_filtro=n["sharpe"]))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{CACHE}/masterclass_swing.pkl")
    pd.set_option("display.width", 250)
    pct = lambda x: f"{x:.1%}"
    print("══════ A) Swing SMA 6/70/200, solo largos (desde que existe la SMA 200) ══════")
    acc = R[R.sector != "índice/ETF/futuro"]
    print(f"Acciones ({len(acc)}): mediana CAGR estrategia {pct(acc.cagr.median())} vs comprar y mantener {pct(acc.cagr_bh.median())}; "
          f"Sharpe {acc.sharpe.median():.2f} vs {acc.sharpe_bh.median():.2f}; peor caída {pct(acc.dd.median())} vs {pct(acc.dd_bh.median())}; "
          f"tiempo dentro {pct(acc.tiempo_dentro.median())}; acierto {pct(acc.acierto.median())}")
    print(f"  la estrategia supera a comprar y mantener en CAGR en {pct((acc.cagr > acc.cagr_bh).mean())} y en Sharpe en {pct((acc.sharpe > acc.sharpe_bh).mean())} de las acciones")
    print(f"  ¿ayudan las condiciones? Sharpe con condiciones {acc.sharpe.median():.2f} vs cruce 6/70 sin condiciones {acc.sharpe_sin_filtro.median():.2f}")
    print("\nPor sector (medianas):")
    print(acc.groupby("sector")[["cagr", "cagr_bh", "sharpe", "sharpe_bh", "dd", "dd_bh", "tiempo_dentro", "ops"]].median().round(3).sort_values("cagr_bh", ascending=False).to_string())
    print("\nÍndices, ETF y futuros:")
    print(R[R.sector == "índice/ETF/futuro"][["simbolo", "ops", "acierto", "media_op", "tiempo_dentro", "cagr", "cagr_bh", "sharpe", "sharpe_bh", "dd", "dd_bh"]].round(3).to_string(index=False))


# ═════════════════════════════════ B) divergencia + 66 % ═════════════════════════════════

@njit(cache=True)
def div_trades(o, h, l, c, v, k, day, win, last, p, maxgap, fr, dtype, cost):
    """dtype: 0 sin divergencia (control), 1 divergencia de volumen, 2 de estocástico, 3 cualquiera.
    Devuelve pnl en puntos, R, lado, día y si la operación alcanzó el objetivo."""
    n = len(c)
    pnl = np.empty(n)
    rr = np.empty(n)
    sd = np.empty(n, np.int64)
    dd = np.empty(n, np.int64)
    hit = np.empty(n, np.bool_)
    nt = 0
    l1i, h1i = -1, -1
    busy = -1
    for i in range(2 * p + 1, n - 1):
        j = i - p
        if day[j] < 0:
            continue
        isl, ish = True, True
        for q in range(j - p, j + p + 1):
            if q == j:
                continue
            if l[q] < l[j] or (q < j and l[q] == l[j]):
                isl = False
            if h[q] > h[j] or (q < j and h[q] == h[j]):
                ish = False
        for s in (1, -1):
            if (s == 1 and not isl) or (s == -1 and not ish):
                continue
            prev = l1i if s == 1 else h1i
            if s == 1:
                l1i = j
            else:
                h1i = j
            if prev < 0 or day[prev] != day[j] or j - prev > maxgap or j - prev < 3:
                continue
            ext2 = l[j] if s == 1 else h[j]
            ext1 = l[prev] if s == 1 else h[prev]
            if not ((s == 1 and ext2 < ext1) or (s == -1 and ext2 > ext1)):
                continue
            vdiv = v[j] < v[prev]
            kdiv = (k[j] > k[prev]) if s == 1 else (k[j] < k[prev])
            isdiv = vdiv if dtype == 1 else kdiv if dtype == 2 else (vdiv or kdiv)
            if dtype == 0:
                if vdiv or kdiv:
                    continue
            elif not isdiv:
                continue
            if not win[i] or i <= busy or day[i] != day[j]:
                continue
            m = -1e18 if s == 1 else 1e18
            for q in range(prev, j + 1):
                m = max(m, h[q]) if s == 1 else min(m, l[q])
            tgt = ext2 + s * fr * abs(m - ext2)
            e = c[i]
            stop = ext2 - s * 0.25          # 1 tic más allá del extremo (NQ 0,25; vale igual para el oro)
            if (s == 1 and (e >= tgt or e <= stop)) or (s == -1 and (e <= tgt or e >= stop)):
                continue
            res = np.nan
            reached = False
            q = i + 1
            while q < n and day[q] == day[i]:
                if (s == 1 and l[q] <= stop) or (s == -1 and h[q] >= stop):
                    res = s * ((min(stop, o[q]) if s == 1 else max(stop, o[q])) - e)
                    break
                if (s == 1 and h[q] >= tgt) or (s == -1 and l[q] <= tgt):
                    res = s * (tgt - e)
                    reached = True
                    break
                if last[q]:
                    res = s * (c[q] - e)
                    break
                q += 1
            if res != res:
                continue
            pnl[nt] = res - cost
            rr[nt] = res / abs(e - stop)
            sd[nt] = s
            dd[nt] = day[i]
            hit[nt] = reached
            nt += 1
            busy = q
    return pnl[:nt], rr[:nt], sd[:nt], dd[:nt], hit[:nt]


def stoch_k(b, n=14, sk=3):
    ll, hh = b.low.rolling(n).min(), b.high.rolling(n).max()
    raw = 100 * (b.close - ll) / (hh - ll).replace(0, np.nan)
    return raw.rolling(sk).mean().fillna(50).to_numpy()


def part_b():
    from vwap_globex_8y import load
    pd.set_option("display.width", 250)
    d1 = load()[["open", "high", "low", "close", "volume"]].sort_index()
    d1.index = d1.index.tz_convert("America/New_York")
    sets = []
    for tf in (5, 1):
        b = d1 if tf == 1 else d1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
        sets.append(("NQ", f"{tf}m", b, (570, 960), 1.0, 2.0))
    g = load_5m("GC")
    g = g.assign(volume=np.nan)
    sets.append(("GC", "5m", g, (180, 810), 0.3, 10.0))
    to_year = lambda x: x.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for sym, tfn, b, (a, z), cost, usd in sets:
        t = b.index
        hm = (t.hour * 60 + t.minute).to_numpy()
        gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
        tf = int(tfn[:-1])
        inw = (hm >= a) & (hm < z)
        day = np.where(inw, gday, -1)
        win = (hm >= a) & (hm <= z - 30)
        last = hm == z - tf
        o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
        v = np.nan_to_num(b.volume.to_numpy().astype(float), nan=0.0)
        k = stoch_k(b)
        dtypes = {"sin divergencia (control)": 0, "divergencia de volumen": 1, "divergencia de estocástico": 2, "cualquiera": 3}
        if sym == "GC":
            dtypes = {"sin divergencia (control)": 0, "divergencia de estocástico": 2}
        for (dn, dt), fr in [(x, f) for x in dtypes.items() for f in (0.5, 0.618, 0.66)]:
            pnl, R, sd, dd, hit = div_trades(o, h, l, c, v, k, day, win, last, 3, 60 // tf * 3 if tf == 5 else 90, fr, dt, cost)
            if len(pnl) < 30:
                continue
            y = to_year(dd)
            u = pnl * usd
            row = dict(activo=sym, tf=tfn, señal=dn, objetivo=f"{fr:.1%}", ops_año=round(len(u) / 8.75),
                       llega_objetivo=round(hit.mean(), 2), acierto=round((u > 0).mean(), 2), R_medio=round(R.mean(), 3))
            for nm_, sel, yrs in (("2018-22", y < 2023, 5), ("2023-26", y >= 2023, 3.75)):
                vv = u[sel]
                row[f"{nm_} $/año"] = round(vv.sum() / yrs)
                row[f"PF {nm_}"] = round(vv[vv > 0].sum() / -vv[vv < 0].sum(), 2)
            eq = np.cumsum(u)
            row["peor racha $"] = round((np.maximum.accumulate(eq) - eq).max())
            rows.append(row)
        print(f"{sym} {tfn} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(f"{CACHE}/masterclass_div.pkl")
    print("\n══════ B) Divergencia + retroceso (dobles mínimos/máximos, fractal de 3 velas) ══════")
    print(R.to_string(index=False))


if __name__ == "__main__":
    part_a()
    part_b()
