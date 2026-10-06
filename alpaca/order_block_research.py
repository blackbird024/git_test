"""Order Blocks en 5 min en NQ / MNQ: ¿tienen ventaja? Búsqueda con validación fuera de muestra.

Definición (la habitual en SMC/ICT, hecha mecánica):
  · OB alcista: la última vela BAJISTA (cierre < apertura) antes de un impulso alcista. Impulso: en las 3 velas
    siguientes el cierre supera el máximo del OB en al menos m·ATR(14, 5 min). Opcional: que además rompa el
    máximo de las 10 velas anteriores (BOS) y/o que deje un FVG (mínimo de la vela 3 > máximo de la vela 1).
  · Zona: del máximo (borde cercano) al mínimo (borde lejano) de esa vela. OB bajista: espejo.
  · Entrada: orden límite al volver a la zona, en el borde cercano o en el 50 %; solo el primer toque;
    el OB caduca a las N velas o si una vela cierra más allá del borde lejano antes del toque.
  · Stop: borde lejano. Objetivo: 1R, 2R, 3R o cierre de la ventana. Una posición a la vez.
Ventanas: NY (OB y entradas 9:30-15:30 NY, todo cerrado a las 16:00) y Londres (07:00-11:30, cierre 12:00 Londres).
Datos: NQ 5 min 2018 - oct 2026 (Databento). Se ELIGE con 2018-2022 y se JUZGA con 2023-2026; control en ES.
Coste 1 punto por operación; resultados por 1 MNQ. Si en la misma vela se tocan stop y objetivo, cuenta el stop.

Uso:
    python order_block_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

COST, USD, SPLIT = 1.0, 2.0, 2023


@njit(cache=True)
def sim(o, h, l, c, atr, sid, form, enter, last, m, bos, fvg, mid, rr, age, cost):
    n = len(o)
    MX = 64
    ob_side = np.zeros(MX, np.int64)
    ob_top = np.zeros(MX)
    ob_bot = np.zeros(MX)
    ob_t = np.zeros(MX, np.int64)
    nob = 0
    pnl = np.empty(n)
    rmul = np.empty(n)
    day = np.empty(n, np.int64)
    nt = 0
    pos, e, sl, tg = 0, 0.0, 0.0, 0.0
    for i in range(14, n):
        if sid[i] < 0:
            continue
        if sid[i] != sid[i - 1]:
            nob = 0
        # gestión de la posición abierta
        if pos != 0:
            out = np.nan
            if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                out = min(sl, o[i]) if pos == 1 else max(sl, o[i])
            elif rr > 0 and ((pos == 1 and h[i] >= tg) or (pos == -1 and l[i] <= tg)):
                out = tg
            elif last[i]:
                out = c[i]
            if not np.isnan(out):
                pnl[nt] = pos * (out - e) - cost
                rmul[nt] = pos * (out - e) / abs(e - sl)
                day[nt] = sid[i]
                nt += 1
                pos = 0
        # entrada: primer toque de un OB vivo (el más reciente primero)
        if pos == 0 and enter[i] and not last[i]:
            for q in range(nob - 1, -1, -1):
                if i - ob_t[q] > age or ob_t[q] >= i:
                    continue
                s = ob_side[q]
                top, bot = ob_top[q], ob_bot[q]
                lvl = (top + bot) / 2 if mid else (top if s == 1 else bot)
                stp = bot if s == 1 else top
                touched = (l[i] <= lvl) if s == 1 else (h[i] >= lvl)
                if not touched:
                    continue
                ob_t[q] = -10 ** 9                 # usado
                fill = min(lvl, o[i]) if s == 1 else max(lvl, o[i])
                if (s == 1 and fill <= stp) or (s == -1 and fill >= stp):
                    continue                        # abrió más allá del stop: no se entra
                pos, e, sl = s, fill, stp
                tg = e + s * rr * abs(e - sl)
                # misma vela: si también toca el stop, se pierde (conservador)
                if (s == 1 and l[i] <= sl) or (s == -1 and h[i] >= sl):
                    pnl[nt] = s * (sl - e) - cost
                    rmul[nt] = -1.0
                    day[nt] = sid[i]
                    nt += 1
                    pos = 0
                break
        # invalidar OB cuyo borde lejano se cierra antes del toque
        for q in range(nob):
            if ob_t[q] > 0 and ((ob_side[q] == 1 and c[i] < ob_bot[q]) or (ob_side[q] == -1 and c[i] > ob_top[q])):
                ob_t[q] = -10 ** 9
        # detección de un OB nuevo: vela j = i-3 seguida de impulso en i-2..i
        j = i - 3
        if form[j] and sid[j] == sid[i] and atr[j] > 0:
            for s in (1, -1):
                if s == 1 and not (c[j] < o[j]):
                    continue
                if s == -1 and not (c[j] > o[j]):
                    continue
                ext = h[j] if s == 1 else l[j]
                best = -1e18
                for k in range(j + 1, i + 1):
                    best = max(best, s * (c[k] - ext))
                if best < m * atr[j] or s * (c[i] - ext) <= 0:
                    continue
                if bos:
                    sw = -1e18 if s == 1 else 1e18
                    for k in range(j - 10, j):
                        sw = max(sw, h[k]) if s == 1 else min(sw, l[k])
                    if s * (c[i] - sw) <= 0:
                        continue
                if fvg:
                    if s == 1 and not (l[j + 2] > h[j]):
                        continue
                    if s == -1 and not (h[j + 2] < l[j]):
                        continue
                if nob == MX:
                    for q in range(MX - 1):
                        ob_side[q], ob_top[q], ob_bot[q], ob_t[q] = ob_side[q + 1], ob_top[q + 1], ob_bot[q + 1], ob_t[q + 1]
                    nob -= 1
                ob_side[nob], ob_top[nob], ob_bot[nob], ob_t[nob] = s, h[j], l[j], i
                nob += 1
    return pnl[:nt], rmul[:nt], day[:nt]


def prepare(sym):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    lmn = (tl.hour * 60 + tl.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    dny = (tn.normalize().asi8 // 86_400_000_000_000).astype(np.int64)
    dld = (tl.normalize().asi8 // 86_400_000_000_000).astype(np.int64)
    W = {
        "NY": (np.where((nm >= 570) & (nm < 960), dny, -1), (nm >= 570) & (nm <= 930), (nm >= 570) & (nm <= 930), nm == 955),
        "Londres": (np.where((lmn >= 420) & (lmn < 720), dld, -1), (lmn >= 420) & (lmn <= 690), (lmn >= 420) & (lmn <= 690), lmn == 715),
    }
    return o, h, l, c, np.nan_to_num(atr), W


def run(sym):
    o, h, l, c, atr, W = prepare(sym)
    rows = []
    for win, m, bos, fvg, mid, rr, age in itertools.product(W, (1.0, 1.5, 2.5), (0, 1), (0, 1), (0, 1), (1.0, 2.0, 3.0, 0.0), (12, 36)):
        sid, form, enter, last = W[win]
        pnl, rm, dd = sim(o, h, l, c, atr, sid, form, enter, last, m, bos, fvg, mid, rr, age, COST)
        if len(pnl) < 50:
            continue
        y = dd.astype("datetime64[D]").astype("datetime64[Y]").astype(int) + 1970
        u = pnl * USD
        r = dict(ventana=win, impulso=f"{m} ATR", bos=bos, fvg=fvg, entrada="50%" if mid else "borde", obj=f"{rr:g}R" if rr else "cierre",
                 vida=f"{age} velas")
        for name, sel, yrs in (("dev", y < SPLIT, 5), ("val", y >= SPLIT, 3.75)):
            v = u[sel]
            g, ls = v[v > 0].sum(), -v[v < 0].sum()
            eq = np.cumsum(v)
            r |= {f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs), f"{name}_pf": round(g / ls, 2) if ls else np.inf}
            if name == "val":
                r |= dict(val_dd=round((np.maximum.accumulate(eq) - eq).max()), val_win=round((v > 0).mean(), 2),
                          val_R=round(rm[sel].mean(), 3))
        by = pd.Series(u).groupby(y).sum()
        r["años"] = f"{(by > 0).sum()}/{len(by)}"
        r["by_year"] = by.round().astype(int).to_dict()
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    pd.set_option("display.width", 250)
    for sym in ("NQ", "ES"):
        r = run(sym)
        r.to_pickle(f".lab_cache/ob_{sym}.pkl")
        both = lambda g: f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}"
        print(f"\n══════ {sym}: {len(r)} variantes, ganan en ambos periodos: {both(r)} ══════")
        for col in ("ventana", "impulso", "bos", "fvg", "entrada", "obj", "vida"):
            print(r.groupby(col).apply(lambda g: pd.Series({"n": len(g), "% ambos": both(g), "med dev": int(g.dev_usd.median()),
                  "med val": int(g.val_usd.median())}), include_groups=False).to_string(), "\n")
        cols = [k for k in r.columns if k != "by_year"]
        print("Mejor de cada ventana ELEGIDA con 2018-2022:")
        print(r.loc[r.groupby("ventana").dev_usd.idxmax(), cols].to_string(index=False))
        print("\nLas 12 con el peor periodo más alto:")
        r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(r.head(12)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
