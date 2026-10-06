"""Sesión de Londres en NQ / MNQ, segunda ronda: más familias, misma validación que london_research.py.

Datos: NQ en velas de 1 min con volumen (Databento, 2018 - oct 2026) agrupadas en 5 min; ES (control) en 5 min
sin volumen, por eso la familia VWAP solo se prueba en NQ. Horas de Londres en hora de Londres.
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026. Coste 1 punto; resultados por 1 MNQ (2 $/punto).
Ventana de operación: desde la hora de entrada hasta 10:00, 12:00 o 14:25 Londres (antes de abrir NY).

Familias nuevas:
  noche      a la hora de entrada, cuánto se ha alejado el precio del cierre de NY de ayer (en ATR diarios):
             si supera un umbral → a favor o en contra hasta la salida
  pdhl       niveles de ayer en NY (máximo / mínimo de 9:30-16:00): en Londres, romperlos o desvanecerlos
  ruido      bandas de ruido (Zarattini) ancladas en la apertura de Londres: a favor de la salida de la banda
  vwap       lado de la VWAP de Globex a la hora de entrada; salida si una vela de 5 min cierra al otro lado
  ema        cruce de EMAs en 15 min / 1 h (calculadas con las 24 h) solo durante la ventana de Londres
  rsi2       RSI de 2 periodos en 15 min: extremos → contra ellos; salida al cruzar 50 o en la hora de salida
  ny_final   dirección de la última hora de NY de ayer → seguirla o ir contra ella en Londres

Uso:
    python london_research2.py
"""

import itertools

import numpy as np
import pandas as pd

import london_research as L1
from crt_backtest import load_5m
from ema_cross_research import align, tf_frame

COST, USD = 1.0, 2.0
EXITS = ("10:00", "12:00", "14:25")


def nq_5m_vol():
    from vwap_globex_8y import load
    d = load()[["open", "high", "low", "close", "volume"]].sort_index()
    d.index = d.index.tz_convert("America/New_York")
    b = d.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return b.dropna(subset=["open"])


def build(sym):
    df = nq_5m_vol() if sym == "NQ" else load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gdate = (tn + pd.Timedelta(hours=6)).normalize().date
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    lm = np.where(np.array(tl.date) < np.array(gdate), lm - 1440, lm)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    nm = np.where(nm >= 1080, nm - 1440, nm)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    # VWAP de Globex (anclada a las 18:00 NY) para cada vela
    if "volume" in df:
        typ = (df.high + df.low + df.close).to_numpy() / 3
        v = df.volume.to_numpy().astype(float)
        g = pd.Series(np.arange(len(df))).groupby(gdate).ngroup().to_numpy()
        pv = pd.Series(typ * v).groupby(g).cumsum().to_numpy()
        vv = pd.Series(v).groupby(g).cumsum().to_numpy()
        vwg = pv / np.maximum(vv, 1)
    else:
        vwg = np.full(len(df), np.nan)
    # EMAs de 15 min y 1 h (última vela cerrada) y RSI(2) de 15 min
    ind = {}
    for tfn, tf in (("15m", 15), ("1h", 60)):
        b = tf_frame(df[["open", "high", "low", "close"]], tf)
        cols = []
        for f, s in ((9, 21), (12, 26), (20, 50)):
            b[f"{tfn}_{f}/{s}"] = np.sign(b.close.ewm(span=f, adjust=False).mean() - b.close.ewm(span=s, adjust=False).mean())
            cols.append(f"{tfn}_{f}/{s}")
        if tf == 15:
            d_ = b.close.diff()
            up = d_.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
            dn = (-d_.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
            b["rsi2"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
            cols.append("rsi2")
        ind |= align(df, b, cols)
    days, prev_rth = [], None
    for d, idx in pd.Series(np.arange(len(df))).groupby(gdate).indices.items():
        idx = np.asarray(idx)
        Lm, Nm = lm[idx], nm[idx]
        rth = (Nm >= 570) & (Nm < 960)
        this_rth = None
        if rth.sum() >= 70:
            r = idx[rth]
            last_hr = idx[(Nm >= 900) & (Nm < 960)]
            this_rth = dict(H=h[r].max(), L=l[r].min(), C=c[r][-1],
                            lh=(c[last_hr][-1] - o[last_hr][0]) if len(last_hr) else 0.0)
        keep = Nm < 600
        ii, Lk, Nk = idx[keep], Lm[keep], Nm[keep]
        ok = len(ii) >= 150 and (Lk == 0).any() and (Lk == 480).any() and (Nk == 565).any()
        if ok and prev_rth is not None:
            x = dict(d=pd.Timestamp(d), o=o[ii], h=h[ii], l=l[ii], c=c[ii], lm=Lk, nm=Nk, vwg=vwg[ii],
                     pH=prev_rth["H"], pL=prev_rth["L"], pC=prev_rth["C"], plh=prev_rth["lh"],
                     rng=h[idx].max() - l[idx].min())
            for k, arr in ind.items():
                x[k] = arr[ii]
            days.append(x)
        prev_rth = this_rth
    atr = pd.Series([x["rng"] for x in days]).rolling(14).mean().shift(1).to_numpy()
    for x, a in zip(days, atr):
        x["atr"] = a
    return [x for x in days if np.isfinite(x["atr"])]


k_at = lambda x, m: int(np.flatnonzero(x["lm"] <= m)[-1])


def noche(days, entry=480, th=0.25, follow=False, ex="14:25", stop=None):
    out = []
    for x in days:
        k = k_at(x, entry)
        z = (x["c"][k] - x["pC"]) / x["atr"]
        if abs(z) < th:
            continue
        side = int(np.sign(z)) * (1 if follow else -1)
        e = x["c"][k]
        sl = e - side * stop * x["atr"] if stop else (-np.inf if side == 1 else np.inf)
        out.append((x["d"], L1.trade(x, k, side, e, sl, None, L1.exit_idx(x, ex))))
    return out


def pdhl(days, start=420, mode="rompe", ex="14:25", stop=0.15):
    out = []
    for x in days:
        ke = L1.exit_idx(x, ex)
        k0 = k_at(x, start)
        if not (x["pL"] < x["c"][k0] < x["pH"]):
            continue
        for k in range(k0 + 1, ke):
            up, dn = x["h"][k] > x["pH"], x["l"][k] < x["pL"]
            if not (up or dn):
                continue
            lvl = x["pH"] if up else x["pL"]
            side = (1 if up else -1) * (1 if mode == "rompe" else -1)
            e = max(lvl, x["o"][k]) if up else min(lvl, x["o"][k])
            sl = e - side * stop * x["atr"]
            out.append((x["d"], L1.trade(x, k, side, e, sl, None, ke)))
            break
    return out


def ruido(days, lookback=14, mult=1.0, step=3, ex="14:25", start=480):
    out = []
    win = []
    for x in days:
        k0 = k_at(x, start)
        ke = L1.exit_idx(x, ex)
        n = ke - k0
        o0 = x["o"][k0 + 1] if k0 + 1 < len(x["o"]) else x["c"][k0]
        mv = np.abs(x["c"][k0 + 1:ke + 1] / o0 - 1)
        if len(win) >= lookback and n > step:
            m = min(n, min(len(w) for w in win[-lookback:]))
            sig = np.mean([w[:m] for w in win[-lookback:]], axis=0) * mult
            pos, e, pnl = 0, 0.0, 0.0
            for j in range(step - 1, m - 1, step):
                k = k0 + 1 + j
                cc, px = x["c"][k], x["o"][k + 1]
                ub, lb = o0 * (1 + sig[j]), o0 * (1 - sig[j])
                if pos == 1 and cc < ub:
                    pnl += px - e - COST; pos = 0
                elif pos == -1 and cc > lb:
                    pnl += e - px - COST; pos = 0
                if pos == 0 and cc > ub:
                    pos, e = 1, px
                elif pos == 0 and cc < lb:
                    pos, e = -1, px
            if pos:
                pnl += pos * (x["c"][k0 + m] - e) - COST
            if pnl:
                out.append((x["d"], pnl))
        win.append(mv)
    return out


def vwap(days, entry=480, only=0, ex="14:25", trail=True):
    out = []
    for x in days:
        if not np.isfinite(x["vwg"]).all():
            continue
        k = k_at(x, entry)
        side = 1 if x["c"][k] > x["vwg"][k] else -1
        if only and side != only:
            continue
        ke = L1.exit_idx(x, ex)
        e = x["c"][k]
        px = x["c"][ke]
        if trail:
            for j in range(k + 1, ke):
                if side * (x["c"][j] - x["vwg"][j]) < 0:
                    px = x["o"][j + 1]
                    break
        out.append((x["d"], side * (px - e) - COST))
    return out


def ema(days, key="1h_12/26", start=480, ex="14:25", fresh=True):
    out = []
    for x in days:
        st = x[key]
        k0 = k_at(x, start)
        ke = L1.exit_idx(x, ex)
        pos, e, n = 0, 0.0, 0
        for k in range(k0, ke):
            cross = st[k] != st[k - 1]
            if pos and st[k] != pos:
                out.append((x["d"], pos * (x["o"][k + 1] - e) - COST)); pos = 0
            if pos == 0 and st[k] != 0 and (cross or (not fresh and k == k0)):
                pos, e = int(st[k]), x["o"][k + 1]
        if pos:
            out.append((x["d"], pos * (x["c"][ke] - e) - COST))
    return out


def rsi2(days, lo=10, start=480, ex="14:25", stop=0.15):
    out = []
    for x in days:
        r = x["rsi2"]
        k0 = k_at(x, start)
        ke = L1.exit_idx(x, ex)
        pos, e, sl = 0, 0.0, 0.0
        for k in range(k0, ke):
            if pos:
                if (pos == 1 and x["l"][k] <= sl) or (pos == -1 and x["h"][k] >= sl):
                    out.append((x["d"], pos * (sl - e) - COST)); pos = 0; continue
                if (pos == 1 and r[k] > 50) or (pos == -1 and r[k] < 50):
                    out.append((x["d"], pos * (x["o"][k + 1] - e) - COST)); pos = 0
            if pos == 0 and np.isfinite(r[k]) and r[k] != r[k - 1]:
                side = 1 if r[k] < lo else -1 if r[k] > 100 - lo else 0
                if side:
                    pos, e = side, x["o"][k + 1]
                    sl = e - side * stop * x["atr"]
        if pos:
            out.append((x["d"], pos * (x["c"][ke] - e) - COST))
    return out


def ny_final(days, follow=True, entry=480, ex="14:25", th=0.0):
    out = []
    for x in days:
        if abs(x["plh"]) <= th * x["atr"] or x["plh"] == 0:
            continue
        side = int(np.sign(x["plh"])) * (1 if follow else -1)
        k = k_at(x, entry)
        out.append((x["d"], L1.trade(x, k, side, x["c"][k], -np.inf if side == 1 else np.inf, None, L1.exit_idx(x, ex))))
    return out


GRID = {
    "noche": [dict(f=noche, entry=en, th=t, follow=fo, ex=e, stop=s) for en, t, fo, e, s in
              itertools.product((420, 480), (0.15, 0.3, 0.5), (True, False), EXITS, (None, 0.2))],
    "pdhl": [dict(f=pdhl, start=s, mode=m, ex=e, stop=st) for s, m, e, st in
             itertools.product((420, 480), ("rompe", "desvanece"), EXITS, (0.1, 0.2))],
    "ruido": [dict(f=ruido, mult=m, step=st, ex=e) for m, st, e in itertools.product((0.8, 1.0, 1.3), (1, 3, 6), EXITS)],
    "vwap": [dict(f=vwap, entry=en, only=o, ex=e, trail=t) for en, o, e, t in
             itertools.product((420, 480, 540, 600), (0, 1), EXITS[1:], (True, False))],
    "ema": [dict(f=ema, key=k, start=s, ex=e, fresh=fr) for k, s, e, fr in
            itertools.product(("15m_9/21", "15m_12/26", "15m_20/50", "1h_9/21", "1h_12/26", "1h_20/50"), (420, 480), EXITS[1:], (True, False))],
    "rsi2": [dict(f=rsi2, lo=lo, start=s, ex=e, stop=st) for lo, s, e, st in
             itertools.product((5, 10, 20), (420, 480), EXITS, (0.1, 0.25))],
    "ny_final": [dict(f=ny_final, follow=fo, entry=en, ex=e, th=t) for fo, en, e, t in
                 itertools.product((True, False), (0, 420, 480), EXITS, (0.0, 0.1))],
}


def run(sym):
    days = build(sym)
    rows = []
    for fam, grid in GRID.items():
        if fam == "vwap" and sym != "NQ":
            continue
        for p in grid:
            q = {k: v for k, v in p.items() if k != "f"}
            r = L1.evaluate(p["f"](days, **q))
            if r:
                rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in q.items()), **r))
        print(f"  {sym} {fam} listo", flush=True)
    return pd.DataFrame(rows), len(days)


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 70)
    for sym in ("NQ", "ES"):
        r, n = run(sym)
        r.to_pickle(f".lab_cache/london2_{sym}.pkl")
        print(f"\n══════════ {sym} ({n} días): $/año por 1 MNQ · dev 2018-2022 · val 2023-2026 ══════════")
        print(r.groupby("fam").apply(lambda g: pd.Series({
            "variantes": len(g), "% gana ambos": f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}",
            "mediana dev": int(g.dev_usd.median()), "mediana val": int(g.val_usd.median())}), include_groups=False).to_string())
        cols = [c for c in r.columns if c != "by_year"]
        print("\nMejor de cada familia ELEGIDA con 2018-2022:")
        print(r.loc[r.groupby("fam").dev_usd.idxmax(), cols].to_string(index=False))
        print("\nLas 15 con el peor periodo más alto:")
        r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(r.head(15)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
