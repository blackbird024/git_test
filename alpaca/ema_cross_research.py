"""Cruce de EMAs en NQ / MNQ: ¿qué par de medias y qué temporalidad (5 min, 15 min, 1 hora) funciona?

Datos: velas de 5 minutos de NQ (Databento, contrato continuo, 24 h), 2018 - oct 2026. Las EMAs se calculan
con todas las horas, como las ve TradingView en MNQ1!. Las temporalidades de 15 min y 1 h salen de las de 5 min,
y una señal solo cuenta cuando la vela de esa temporalidad ha CERRADO. Entradas y salidas se simulan con velas
de 5 min (precio de apertura de la vela siguiente; stops intrabarra al nivel).

Reglas base: EMA rápida cruza por encima de la lenta → largo; por debajo → corto (o solo salir, en "solo largos").
Variantes:
  ventana   NY: entradas 9:30-15:30, todo cerrado a las 16:00 · Globex: entradas 18:00-16:00, cerrado a las 17:00
  lado      ambos / solo largos
  filtro    ninguno / solo a favor de la EMA 200 de la misma temporalidad
  stop      ninguno / 1,5 ATR / 3 ATR (ATR 14 de la temporalidad); tras un stop se espera al siguiente cruce
  entrada   solo cruces nuevos / también el estado de las medias al abrir la ventana
Método: la variante se ELIGE con 2018-2022 y se JUZGA con 2023-2026. Se mira también qué fracción de cada
rejilla gana en cada periodo y se repite en ES como control. Coste 1 punto por operación; resultados por 1 MNQ.

Requiere numba (pip install numba).

Uso:
    python ema_cross_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

COST = 1.0
USD = 2.0
SPLIT = 2023
PAIRS = [(5, 13), (8, 21), (9, 21), (9, 30), (12, 26), (13, 48), (20, 50), (21, 55), (50, 200)]
TFS = {"5m": 5, "15m": 15, "1h": 60}


def tf_frame(df, tf):
    if tf == 5:
        b = df.copy()
    else:
        b = df.resample(f"{tf}min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    pc = b.close.shift()
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    b["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    b["e200"] = b.close.ewm(span=200, adjust=False).mean()
    b["tclose"] = b.index + pd.Timedelta(minutes=tf)
    return b


def align(b5, b, cols):
    """Valor de la última vela de la temporalidad ya cerrada al cierre de cada vela de 5 min."""
    k = np.searchsorted(b.tclose.to_numpy(), (b5.index + pd.Timedelta(minutes=5)).to_numpy(), side="right") - 1
    return {c: np.where(k >= 0, b[c].to_numpy()[np.maximum(k, 0)], np.nan) for c in cols}


@njit(cache=True)
def sim(o, h, l, c, st, tr, atr, day, can, last, longonly, filt, stopm, fresh, cost):
    n = len(o)
    pnl = np.empty(n)
    dd = np.empty(n, np.int64)
    nt = 0
    pos, e, stop, blocked = 0, 0.0, 0.0, 0
    for i in range(1, n - 1):
        if day[i] != day[i - 1]:
            blocked = 1 if fresh else 0            # nueva sesión: con "cruce" se espera a un cruce dentro de ella
            if pos != 0:                           # sesión sin su última vela (festivo): se cierra en la anterior
                pnl[nt] = pos * (c[i - 1] - e) - cost
                dd[nt] = day[i - 1]
                nt += 1
                pos = 0
        elif st[i] != st[i - 1]:
            blocked = 0
        if pos != 0:
            if stopm > 0 and ((pos == 1 and l[i] <= stop) or (pos == -1 and h[i] >= stop)):
                px = min(stop, o[i]) if pos == 1 else max(stop, o[i])
                pnl[nt] = pos * (px - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
                blocked = 1
            elif last[i]:
                pnl[nt] = pos * (c[i] - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
            elif st[i] != pos:
                pnl[nt] = pos * (o[i + 1] - e) - cost
                dd[nt] = day[i]
                nt += 1
                pos = 0
        if pos == 0 and can[i] and not last[i] and blocked == 0 and st[i] != 0:
            want = int(st[i])
            if longonly and want == -1:
                continue
            if filt and tr[i] != want:
                continue
            pos = want
            e = o[i + 1]
            stop = e - pos * stopm * atr[i]
    return pnl[:nt], dd[:nt]


def prepare(sym):
    df = load_5m(sym)
    t = df.index
    hm = (t.hour * 60 + t.minute).to_numpy()
    gday = ((t + pd.Timedelta(hours=6)).normalize()).asi8 // 86_400_000_000_000
    out = {}
    for tfn, tf in TFS.items():
        b = tf_frame(df, tf)
        cl = b.close
        emas = {p: cl.ewm(span=p, adjust=False).mean() for p in sorted({x for pr in PAIRS for x in pr})}
        for f, s in PAIRS:
            b[f"s{f}_{s}"] = np.sign(emas[f] - emas[s])
        b["tr"] = np.sign(cl - b.e200)
        out[tfn] = align(df, b, ["atr", "tr"] + [f"s{f}_{s}" for f, s in PAIRS])
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    # ventanas
    ny = (hm >= 570) & (hm < 960)
    ny_can = (hm >= 570) & (hm <= 930)
    ny_day = np.where(ny, gday, -1)
    ny_last = ny & (hm == 955)
    gx = (hm >= 1080) | (hm < 1020)
    gx_can = (hm >= 1080) | (hm < 960)
    gx_last = hm == 1015
    year = t.year.to_numpy()
    wins = {"NY": (ny, ny_can, ny_last), "Globex": (gx, gx_can, gx_last)}
    return dict(o=o, h=h, l=l, c=c, gday=gday, wins=wins, tf=out, year=year)


def evaluate(pnl, dday, gday_year):
    y = gday_year(dday)
    usd = pnl * USD
    r = {}
    for name, sel in (("dev", y < SPLIT), ("val", y >= SPLIT)):
        u = usd[sel]
        yrs = len(np.unique(y[sel])) if name == "dev" else 3.75
        g, ls = u[u > 0].sum(), -u[u < 0].sum()
        eq = np.cumsum(u)
        r[name] = dict(ops_y=len(u) / yrs, usd_y=u.sum() / yrs, pf=g / ls if ls else np.inf,
                       dd=(np.maximum.accumulate(eq) - eq).max() if len(eq) else 0, win=(u > 0).mean() if len(u) else 0)
    by = pd.Series(usd).groupby(y).sum()
    r["years_pos"] = f"{(by > 0).sum()}/{len(by)}"
    r["by_year"] = by.round(0).astype(int).to_dict()
    return r


def run(sym):
    P = prepare(sym)
    to_year = lambda dd: dd.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
    rows = []
    for tfn, wn, (f, s), lo, fl, sm, fr in itertools.product(TFS, P["wins"], PAIRS, (0, 1), (0, 1), (0.0, 1.5, 3.0), (1, 0)):
        win, can, last = P["wins"][wn]
        A = P["tf"][tfn]
        st = np.nan_to_num(A[f"s{f}_{s}"])
        idx = np.flatnonzero(win)
        day = np.where(win, P["gday"], -1)[idx]
        pnl, dd = sim(P["o"][idx], P["h"][idx], P["l"][idx], P["c"][idx], st[idx], np.nan_to_num(A["tr"])[idx],
                      np.nan_to_num(A["atr"])[idx], day, can[idx], last[idx], lo, fl, sm, fr, COST)
        if len(pnl) < 50:
            continue
        r = evaluate(pnl, dd, to_year)
        rows.append(dict(tf=tfn, ventana=wn, emas=f"{f}/{s}", lado="largos" if lo else "ambos", filtro="EMA200" if fl else "-",
                         stop=f"{sm} ATR" if sm else "-", entrada="cruce" if fr else "estado",
                         dev_ops=round(r["dev"]["ops_y"]), dev_usd=round(r["dev"]["usd_y"]), dev_pf=round(r["dev"]["pf"], 2),
                         val_ops=round(r["val"]["ops_y"]), val_usd=round(r["val"]["usd_y"]), val_pf=round(r["val"]["pf"], 2),
                         val_dd=round(r["val"]["dd"]), val_win=round(r["val"]["win"], 2), años_pos=r["years_pos"],
                         by_year=r["by_year"]))
    return pd.DataFrame(rows)


def report(r, sym):
    print(f"\n══════════ {sym}: $/año por 1 MNQ · desarrollo 2018-2022 · validación 2023-2026 ══════════")
    g = r.groupby(["tf", "ventana"])
    print(g.apply(lambda x: pd.Series({"variantes": len(x), "% gana dev": f"{(x.dev_usd > 0).mean():.0%}",
                                       "% gana val": f"{(x.val_usd > 0).mean():.0%}",
                                       "% gana ambos": f"{((x.dev_usd > 0) & (x.val_usd > 0)).mean():.0%}",
                                       "mediana dev": int(x.dev_usd.median()), "mediana val": int(x.val_usd.median())}),
                  include_groups=False).to_string())
    cols = ["tf", "ventana", "emas", "lado", "filtro", "stop", "entrada", "dev_ops", "dev_usd", "dev_pf", "val_ops",
            "val_usd", "val_pf", "val_dd", "val_win", "años_pos"]
    print("\nMejor variante de cada temporalidad ELEGIDA con 2018-2022 → su resultado en 2023-2026:")
    print(r.loc[r.groupby("tf").dev_usd.idxmax(), cols].to_string(index=False))
    print("\nLas 15 con mejor resultado en AMBOS periodos (el peor de los dos más alto):")
    r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1))
    print(r.sort_values("minimo", ascending=False).head(15)[cols].to_string(index=False))


def main():
    pd.set_option("display.width", 250)
    for sym in ("NQ", "ES"):
        r = run(sym)
        r.to_pickle(f".lab_cache/ema_cross_{sym}.pkl")
        report(r, sym)


if __name__ == "__main__":
    main()
