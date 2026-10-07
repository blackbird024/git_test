"""Búsqueda de una estrategia intradía con ≥ 80 % de acierto Y esperanza positiva (NQ / MNQ y oro / MGC).

Un 80 % de acierto se consigue con cualquier entrada poniendo un objetivo pequeño y un stop grande; lo difícil
es que además gane dinero. Por eso:
  · Se prueban varias ENTRADAS (algunas con ventaja demostrada en este repositorio, otras clásicas y una
    aleatoria como control) con una rejilla de objetivo y stop medidos en fracción del ATR diario.
  · Se exige: acierto ≥ 80 % Y beneficio > 0 Y PF > 1,1, en 2018-2022 (desarrollo) y en 2023-2026 (validación).
  · Costes incluidos (NQ 1 punto, oro 0,3 puntos). La operación que llega a la hora de cierre sin tocar nada
    se cierra a mercado (cuenta como acierto solo si gana).
Datos: NQ velas de 1 min con volumen (2018 - oct 2026); oro velas de 5 min. Si stop y objetivo caen en la
misma vela, cuenta el stop.

Entradas (sesión regular; en oro la de COMEX 8:20-13:30 NY):
  pdr       ruptura del máximo/mínimo de ayer (si se abre dentro del rango), orden STOP en el nivel
  ib        ruptura del rango de la primera hora (Initial Balance), orden STOP en el nivel
  orb5      dirección de la primera vela de 5 min, entrada a la apertura de la segunda
  hueco     apertura con hueco frente al cierre de ayer: entrar hacia el cierre de ayer (llenado del hueco)
  vwap      lado de la VWAP de Globex a las 11:00 (solo NQ, necesita volumen)
  extension el precio se aleja > X ATR de la apertura antes de las 11:00 → a favor (continuación) o en contra
  azar      dirección y hora al azar (control: muestra cuánto acierto da solo la forma del objetivo/stop)

Uso:
    python high_winrate_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

TGT = (0.02, 0.03, 0.05, 0.08, 0.12)
STP = (0.05, 0.08, 0.12, 0.2, 0.3, 0.5)


@njit(cache=True)
def bracket(o, h, l, c, k, side, e, tgt, stp, xe, cost):
    n = len(k)
    pnl = np.empty(n)
    for j in range(n):
        s, p, T, S = side[j], e[j], tgt[j], stp[j]
        res = np.nan
        for i in range(k[j] + 1, xe[j] + 1):
            if (s == 1 and l[i] <= p - S) or (s == -1 and h[i] >= p + S):
                res = -S if (s == 1 and o[i] > p - S) or (s == -1 and o[i] < p + S) else s * (o[i] - p)
                break
            if (s == 1 and h[i] >= p + T) or (s == -1 and l[i] <= p - T):
                res = T
                break
        if res != res:
            res = s * (c[xe[j]] - p)
        pnl[j] = res - cost
    return pnl


def load(sym):
    if sym == "NQ":
        from vwap_globex_8y import load as l1
        d = l1()[["open", "high", "low", "close", "volume"]].sort_index()
        d.index = d.index.tz_convert("America/New_York")
        return d, (570, 960), 1
    return load_5m("GC"), (500, 810), 5


def days_of(df, sess, res):
    t = df.index
    nm = (t.hour * 60 + t.minute).to_numpy()
    nm2 = np.where(nm >= 1080, nm - 1440, nm)
    g = (t + pd.Timedelta(hours=6)).normalize()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    vol = df["volume"].to_numpy().astype(float) if "volume" in df else None
    out, prev = [], None
    a, b = sess
    for d, idx in pd.Series(np.arange(len(df))).groupby(g).indices.items():
        idx = np.asarray(idx)
        m = nm2[idx]
        r = idx[(m >= a) & (m < b)]
        if len(r) < (b - a) // res * 0.95:
            prev = None
            continue
        x = dict(d=pd.Timestamp(d), r=r, H=h[r].max(), L=l[r].min(), C=c[r[-1]], mm=m[(m >= a) & (m < b)])
        if vol is not None:
            gi = idx[m < b]
            pv = np.cumsum((h[gi] + l[gi] + c[gi]) / 3 * vol[gi])
            vv = np.cumsum(vol[gi])
            vw = pv / np.maximum(vv, 1)
            x["vw"] = vw[np.searchsorted(gi, r)]
        if prev is not None:
            x["pH"], x["pL"], x["pC"] = prev["H"], prev["L"], prev["C"]
            out.append(x)
        prev = x
    atr = pd.Series([x["H"] - x["L"] for x in out]).rolling(14).mean().shift(1).to_numpy()
    for x, v in zip(out, atr):
        x["atr"] = v
    return [x for x in out if np.isfinite(x["atr"])]


def entries(days, o, h, l, c, res, sym, rng):
    """Devuelve {nombre: (k, side, precio, atr, xe, año)}."""
    E = {}

    def add(name, k, s, p, x):
        E.setdefault(name, []).append((k, s, p, x["atr"], x["r"][-1], x["d"].year))

    for x in days:
        r, mm = x["r"], x["mm"]
        lastk = lambda minute: r[mm <= minute][-1]
        end_entry = x["mm"][-1] - 30
        # pdr
        if x["pL"] <= o[r[0]] <= x["pH"]:
            for k in r[1:]:
                if (k - r[0]) * res > (x["mm"][-1] - x["mm"][0]) - 30:
                    break
                if h[k] > x["pH"]:
                    add("pdr", k, 1, max(x["pH"], o[k]), x); break
                if l[k] < x["pL"]:
                    add("pdr", k, -1, min(x["pL"], o[k]), x); break
        # ib
        ib = r[mm < mm[0] + 60]
        H, L = h[ib].max(), l[ib].min()
        for k in r[len(ib):]:
            if mm[k - r[0]] > end_entry:
                break
            if h[k] > H:
                add("ib", k, 1, max(H, o[k]), x); break
            if l[k] < L:
                add("ib", k, -1, min(L, o[k]), x); break
        # orb5
        f = r[mm < mm[0] + 5]
        s = int(np.sign(c[f[-1]] - o[f[0]]))
        if s:
            add("orb5", f[-1], s, o[f[-1] + 1], x)
        # hueco
        gap = o[r[0]] - x["pC"]
        if abs(gap) > 0.05 * x["atr"]:
            add("hueco", r[0], -int(np.sign(gap)), o[r[0]], x)
        # vwap
        if "vw" in x:
            k = lastk(660)
            add("vwap", k, 1 if c[k] > x["vw"][k - r[0]] else -1, c[k], x)
        # extension
        for th in (0.25, 0.4):
            for k in r[r <= lastk(660)]:
                dv = c[k] - o[r[0]]
                if abs(dv) > th * x["atr"]:
                    add(f"extension {th} a favor", k, int(np.sign(dv)), c[k], x)
                    add(f"extension {th} en contra", k, -int(np.sign(dv)), c[k], x)
                    break
        # azar
        k = rng.choice(r[: len(r) - 30 // res])
        add("azar", k, int(rng.choice([-1, 1])), c[k], x)
    return {n: tuple(np.array(v) for v in zip(*rows)) for n, rows in E.items()}


def main():
    pd.set_option("display.width", 250)
    rng = np.random.default_rng(7)
    rows = []
    for sym, cost, usd in (("NQ", 1.0, 2.0), ("GC", 0.3, 10.0)):
        df, sess, res = load(sym)
        days = days_of(df, sess, res)
        o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
        E = entries(days, o, h, l, c, res, sym, rng)
        for name, (k, s, p, atr, xe, y) in E.items():
            for tf, sf in itertools.product(TGT, STP):
                pnl = bracket(o, h, l, c, k.astype(np.int64), s.astype(np.int64), p.astype(float), tf * atr, sf * atr,
                              xe.astype(np.int64), cost)
                r = dict(activo=sym, entrada=name, objetivo=f"{tf} ATR", stop=f"{sf} ATR")
                for nm_, sel, yrs in (("dev", y < 2023, 5), ("val", y >= 2023, 3.75)):
                    v = pnl[sel] * usd
                    g, ls = v[v > 0].sum(), -v[v < 0].sum()
                    eq = np.cumsum(v)
                    r |= {f"{nm_}_win": round((v > 0).mean(), 3), f"{nm_}_ops": round(len(v) / yrs), f"{nm_}_usd": round(v.sum() / yrs),
                          f"{nm_}_pf": round(g / ls, 2) if ls else np.inf}
                    if nm_ == "val":
                        r["val_dd"] = round((np.maximum.accumulate(eq) - eq).max())
                by = pd.Series(pnl * usd).groupby(y).sum()
                r["años"] = f"{(by > 0).sum()}/{len(by)}"
                r["by_year"] = by.round().astype(int).to_dict()
                r["obj_pts_2026"] = round(tf * np.median(atr[y == 2026]), 1)
                r["stop_pts_2026"] = round(sf * np.median(atr[y == 2026]), 1)
                rows.append(r)
        print(f"{sym} listo", flush=True)
    R = pd.DataFrame(rows)
    R.to_pickle(".lab_cache/high_winrate.pkl")
    ok = R[(R.dev_win >= 0.8) & (R.val_win >= 0.8) & (R.dev_usd > 0) & (R.val_usd > 0) & (R.dev_pf > 1.1) & (R.val_pf > 1.1)]
    cols = [k for k in R.columns if k != "by_year"]
    print(f"\nCombinaciones con ≥80 % de acierto en ambos periodos: {((R.dev_win >= .8) & (R.val_win >= .8)).sum()} de {len(R)}")
    print("…y que además ganan dinero con PF > 1,1 en ambos periodos:", len(ok))
    print(ok.sort_values("val_usd", ascending=False)[cols].to_string(index=False))
    print("\nControl (entrada al azar), las de ≥80 % de acierto:")
    z = R[(R.entrada == "azar") & (R.dev_win >= 0.8)]
    print(z[cols].to_string(index=False))
    print("\nMejor esperanza por entrada con acierto ≥ 75 % en ambos periodos:")
    w = R[(R.dev_win >= 0.75) & (R.val_win >= 0.75)]
    w = w.assign(mn=w[["dev_usd", "val_usd"]].min(axis=1))
    print(w.loc[w.groupby(["activo", "entrada"]).mn.idxmax(), cols].to_string(index=False))
    for _, x in ok.sort_values("val_usd", ascending=False).head(5).iterrows():
        print(x.activo, x.entrada, x.objetivo, x.stop, x.by_year)


if __name__ == "__main__":
    main()
