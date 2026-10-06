"""Conceptos ICT hechos mecánicos y probados en NQ / MNQ, con validación fuera de muestra.

Reglas tomadas de las descripciones públicas habituales (LuxAlgo, TradingFinder, guías de Silver Bullet / Model
2022 / Unicorn / OTE / Judas / PO3 / Opening Range Gap). Todo se opera dentro del día y cierra a las 16:00 NY.

1. Motor «barrida → MSS → entrada» (Model 2022, Silver Bullet, OTE, Unicorn):
   · Barrida de liquidez:
       externa  supera el nivel más cercano por encima/debajo al empezar la ventana entre: máximo/mínimo del día
                anterior (sesión Globex), Asia (20:00-00:00 NY) y Londres (02:00-05:00 NY)
       interna  supera el último máximo/mínimo de swing (fractal de 3 velas a cada lado)
       ninguna  sin barrida (solo MSS + FVG; sirve para ver si la barrida añade algo)
   · MSS: tras barrer un máximo, una vela CIERRA por debajo del mínimo del tramo que llevó a ese máximo
     (mínimo de las N velas anteriores al extremo), en menos de 30 min. Espejo para largos.
   · Desplazamiento: el tramo extremo → MSS debe dejar un FVG (3 velas: mínimo de la 1.ª > máximo de la 3.ª).
   · Entrada (orden límite, hasta 30 min tras el MSS y dentro de la ventana):
       fvg       borde cercano del FVG          ce       50 % del FVG (consequent encroachment)
       ote       70,5 % del tramo (OTE 62-79)   unicorn  solape del FVG con el breaker (última vela contraria
                                                         en el swing que se rompe); si no solapan, no hay entrada
       mercado   apertura de la vela siguiente al MSS
   · Stop: más allá del extremo barrido, o del máximo/mínimo de la 1.ª vela del FVG.
   · Objetivo: 2R, 3R, la liquidez opuesta (nivel externo más cercano al otro lado, solo si da ≥ 2R) o el cierre.
   · Ventanas (hora NY): Silver Bullet Londres 3-4, AM 10-11, PM 14-15; killzones Londres 2-5 y NY 8:30-11.
   · Temporalidad de las velas: 1 min y 5 min (NQ). Máximo 2 operaciones por ventana y día.
2. Judas / sesgo de la apertura de medianoche: a la hora T, precio por debajo de la apertura de las 00:00 NY
   → largo (descuento), por encima → corto (prima); o al revés (seguirlo). Cierre 16:00.
3. PO3 / AMD diario: a la hora T, si el mínimo del día (desde las 00:00) se hizo por debajo de la apertura de
   medianoche y el precio ya está por encima → largo con stop en ese mínimo (espejo para cortos).
4. Opening Range Gap: hueco entre el cierre de las 16:00 y la apertura de las 9:30; entrar contra el hueco
   para llenarlo (objetivo el CE o el cierre de ayer), o a favor si se rechaza el CE.

Datos: NQ 1 min 2018 - oct 2026 (Databento); ES 5 min como control (sin 1 min antes de 2024).
Se ELIGE con 2018-2022 y se JUZGA con 2023-2026. Coste 1 punto por operación; resultados por 1 MNQ.

Uso:
    python ict_research.py
"""

import itertools

import numpy as np
import pandas as pd
from numba import njit

from crt_backtest import load_5m

COST, USD, SPLIT = 1.0, 2.0, 2023
WINDOWS = {"SB Londres 3-4": (180, 240), "SB AM 10-11": (600, 660), "SB PM 14-15": (840, 900),
           "KZ Londres 2-5": (120, 300), "KZ NY 8:30-11": (510, 660)}


# ───────────────────────── datos ─────────────────────────

def bars(sym, res):
    if sym == "NQ":
        from vwap_globex_8y import load
        d = load()[["open", "high", "low", "close"]].sort_index()
        d.index = d.index.tz_convert("America/New_York")
        if res > 1:
            d = d.resample(f"{res}min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        return d
    assert res == 5
    return load_5m(sym)


def day_table(df, res):
    """Por cada día Globex: índices de las ventanas, niveles de liquidez y referencias de apertura."""
    t = df.index
    nm = (t.hour * 60 + t.minute).to_numpy()
    nm2 = np.where(nm >= 1080, nm - 1440, nm)          # minutos desde la medianoche NY del día Globex (18:00 = -360)
    g = (t + pd.Timedelta(hours=6)).normalize()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rows, prev = [], None
    for d, idx in pd.Series(np.arange(len(df))).groupby(g).indices.items():
        idx = np.asarray(idx)
        m = nm2[idx]
        if len(idx) < 600 // res or not ((m == 570).any() and (m == 960 - res).any() and (m == 0).any()):
            prev = None
            continue
        sel = lambda a, b: idx[(m >= a) & (m < b)]
        asia, ldn, rth = sel(-240, 0), sel(120, 300), sel(570, 960)
        x = dict(d=pd.Timestamp(d), i0=idx[0], mid=idx[m == 0][0], rth0=rth[0], rth1=rth[-1],
                 asiaH=h[asia].max() if len(asia) else np.nan, asiaL=l[asia].min() if len(asia) else np.nan,
                 ldnH=h[ldn].max() if len(ldn) else np.nan, ldnL=l[ldn].min() if len(ldn) else np.nan,
                 dayH=h[idx].max(), dayL=l[idx].min(), rthC=c[rth[-1]])
        x["idx_of"] = {int(mm): int(ii) for mm, ii in zip(m, idx)}
        if prev is not None:
            x["pdH"], x["pdL"], x["pC"] = prev["dayH"], prev["dayL"], prev["rthC"]
            rows.append(x)
        prev = x
    return rows


def at(x, minute):
    """Índice de la última vela que empieza en o antes de ese minuto (NY, desde medianoche)."""
    ks = [k for k in x["idx_of"] if k <= minute]
    return x["idx_of"][max(ks)] if ks else -1


# ───────────────────────── motor barrida → MSS → entrada ─────────────────────────

@njit(cache=True)
def engine(o, h, l, c, scan0, win0, win1, xe, lvh, lvl, liq, leg, kmss, kent, emode, smode, tmode, rr, maxn, piv, cost):
    nd = len(scan0)
    pnl = np.empty(nd * maxn)
    rmul = np.empty(nd * maxn)
    dday = np.empty(nd * maxn, np.int64)
    dside = np.empty(nd * maxn, np.int64)
    nt = 0
    for d in range(nd):
        a, w0, w1, x1 = scan0[d], win0[d], win1[d], xe[d]
        if a < 0 or w0 < 0 or w1 <= w0 or x1 <= w1:
            continue
        ntr = 0
        swept_hi = False
        swept_lo = False
        # estado por lado: 0 nada, 1 barrido (esperando MSS); s=+1 setup largo (tras barrer mínimo), -1 corto
        st_s = np.zeros(2, np.int64)
        ext = np.zeros(2)
        ext_i = np.zeros(2, np.int64)
        mss = np.zeros(2)
        mss_b = np.zeros(2, np.int64)
        t_sw = np.zeros(2, np.int64)
        ph, pl = np.nan, np.nan               # últimos pivotes confirmados (liquidez interna)
        pend, pe, ps, pt, pexp = 0, 0.0, 0.0, 0.0, 0
        pos, e, sl, tg = 0, 0.0, 0.0, 0.0
        for i in range(a, x1 + 1):
            # 1) posición abierta
            if pos != 0:
                out = np.nan
                if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                    out = min(sl, o[i]) if pos == 1 else max(sl, o[i])
                elif tg == tg and ((pos == 1 and h[i] >= tg) or (pos == -1 and l[i] <= tg)):
                    out = tg
                elif i == x1:
                    out = c[i]
                if out == out:
                    pnl[nt] = pos * (out - e) - cost
                    rmul[nt] = pos * (out - e) / abs(e - sl)
                    dday[nt] = d
                    dside[nt] = pos
                    nt += 1
                    pos = 0
                continue
            if i >= w1 or ntr >= maxn:
                if pend == 0:
                    continue
                pend = 0
                continue
            # 2) orden pendiente
            if pend != 0:
                if i > pexp or (pend == 1 and tg == tg and h[i] >= tg) or (pend == -1 and tg == tg and l[i] <= tg):
                    pend = 0
                elif (pend == 1 and l[i] <= pe) or (pend == -1 and h[i] >= pe):
                    fill = min(pe, o[i]) if pend == 1 else max(pe, o[i])
                    if (pend == 1 and fill > ps) or (pend == -1 and fill < ps):
                        pos, e, sl = pend, fill, ps
                        if tmode == 0:
                            tg = e + pos * rr * abs(e - sl)
                        ntr += 1
                        pend = 0
                        if (pos == 1 and l[i] <= sl) or (pos == -1 and h[i] >= sl):
                            pnl[nt] = -abs(e - sl) - cost
                            rmul[nt] = -1.0
                            dday[nt] = d
                            dside[nt] = pos
                            nt += 1
                            pos = 0
                    else:
                        pend = 0
                    continue
            # 3) pivotes internos (confirmados con piv velas a cada lado)
            j = i - piv
            if j - piv >= a:
                isph, ispl = True, True
                for k in range(j - piv, j + piv + 1):
                    if h[k] > h[j]:
                        isph = False
                    if l[k] < l[j]:
                        ispl = False
                if isph:
                    ph = h[j]
                if ispl:
                    pl = l[j]
            # 4) barridas
            for sd in range(2):                 # sd 0: barrida de máximo → corto ; sd 1: barrida de mínimo → largo
                s = -1 if sd == 0 else 1
                if liq == 0:
                    # sin barrida: el «extremo» es el máximo/mínimo de las leg velas anteriores
                    if i - leg - 1 < a:
                        continue
                    best = h[i - 1] if s == -1 else l[i - 1]
                    bi = i - 1
                    for k in range(i - leg, i):
                        if (s == -1 and h[k] > best) or (s == 1 and l[k] < best):
                            best = h[k] if s == -1 else l[k]
                            bi = k
                    st_s[sd] = 1
                    ext[sd] = best
                    ext_i[sd] = bi
                    t_sw[sd] = i
                    lo = 1e18 if s == -1 else -1e18
                    for k in range(max(a, bi - leg), bi):
                        if (s == -1 and l[k] < lo) or (s == 1 and h[k] > lo):
                            lo = l[k] if s == -1 else h[k]
                            mss_b[sd] = k
                    mss[sd] = lo
                elif st_s[sd] == 0:
                    if liq == 1:
                        lv = lvh[d] if s == -1 else lvl[d]
                        done = swept_hi if s == -1 else swept_lo
                        hit = (not done) and lv == lv and ((s == -1 and h[i] > lv) or (s == 1 and l[i] < lv))
                        if hit:
                            if s == -1:
                                swept_hi = True
                            else:
                                swept_lo = True
                    else:
                        lv = ph if s == -1 else pl
                        hit = lv == lv and ((s == -1 and h[i] > lv) or (s == 1 and l[i] < lv))
                        if hit:
                            if s == -1:
                                ph = np.nan
                            else:
                                pl = np.nan
                    if hit:
                        st_s[sd] = 1
                        ext[sd] = h[i] if s == -1 else l[i]
                        ext_i[sd] = i
                        t_sw[sd] = i
                        lo = 1e18 if s == -1 else -1e18
                        for k in range(max(a, i - leg), i):
                            if (s == -1 and l[k] < lo) or (s == 1 and h[k] > lo):
                                lo = l[k] if s == -1 else h[k]
                                mss_b[sd] = k
                        mss[sd] = lo
                else:
                    # el extremo se alarga: se recalcula el nivel del MSS
                    if (s == -1 and h[i] > ext[sd]) or (s == 1 and l[i] < ext[sd]):
                        ext[sd] = h[i] if s == -1 else l[i]
                        ext_i[sd] = i
                        lo = 1e18 if s == -1 else -1e18
                        for k in range(max(a, i - leg), i):
                            if (s == -1 and l[k] < lo) or (s == 1 and h[k] > lo):
                                lo = l[k] if s == -1 else h[k]
                                mss_b[sd] = k
                        mss[sd] = lo
                    if i - t_sw[sd] > kmss:
                        st_s[sd] = 0
                        continue
                # 5) MSS
                if st_s[sd] == 1 and i > ext_i[sd] and ((s == -1 and c[i] < mss[sd]) or (s == 1 and c[i] > mss[sd])):
                    st_s[sd] = 0
                    if i < w0 or pend != 0:
                        continue
                    # FVG del tramo (el más reciente)
                    fk = -1
                    for k in range(i, ext_i[sd] + 1, -1):
                        if (s == -1 and l[k - 2] > h[k]) or (s == 1 and h[k - 2] < l[k]):
                            fk = k
                            break
                    if fk < 0:
                        continue
                    top = l[fk - 2] if s == -1 else l[fk]
                    bot = h[fk] if s == -1 else h[fk - 2]
                    if emode == 0:
                        lvl_e = bot if s == -1 else top
                    elif emode == 1:
                        lvl_e = (top + bot) / 2
                    elif emode == 2:
                        far = 1e18 if s == -1 else -1e18
                        for k in range(ext_i[sd], i + 1):
                            far = min(far, l[k]) if s == -1 else max(far, h[k])
                        lvl_e = far + 0.705 * (ext[sd] - far)
                    elif emode == 3:
                        # breaker: última vela contraria alrededor del swing roto
                        bc = -1
                        for k in range(mss_b[sd], max(a, mss_b[sd] - 4) - 1, -1):
                            if (s == -1 and c[k] < o[k]) or (s == 1 and c[k] > o[k]):
                                bc = k
                                break
                        if bc < 0:
                            continue
                        ob_lo, ob_hi = max(bot, l[bc]), min(top, h[bc])
                        if ob_lo >= ob_hi:
                            continue
                        lvl_e = ob_lo if s == -1 else ob_hi
                    else:
                        lvl_e = o[i + 1]
                    stop = ext[sd] if smode == 0 else (h[fk - 2] if s == -1 else l[fk - 2])
                    if (s == -1 and stop <= lvl_e) or (s == 1 and stop >= lvl_e):
                        continue
                    risk = abs(stop - lvl_e)
                    if tmode == 1:
                        tgt = lvl[d] if s == -1 else lvh[d]
                        if not (tgt == tgt) or s * (tgt - lvl_e) < 2 * risk:
                            continue
                        tg = tgt
                    elif tmode == 2:
                        tg = np.nan
                    else:
                        tg = lvl_e + s * rr * risk
                    pend, pe, ps, pexp = s, lvl_e, stop, i + kent
    return pnl[:nt], rmul[:nt], dday[:nt], dside[:nt]


def run_engine(sym, res):
    df = bars(sym, res)
    days = day_table(df, res)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    dates = np.array([x["d"].year for x in days])
    rows = []
    for wn, (w0, w1) in WINDOWS.items():
        scan0 = np.array([at(x, w0 - 30) for x in days])
        win0 = np.array([at(x, w0) for x in days])
        win1 = np.array([at(x, w1) for x in days])
        xe = np.array([x["rth1"] for x in days])
        # liquidez externa más cercana por encima/debajo del precio al empezar la ventana
        lvh, lvl = [], []
        for x, k in zip(days, scan0):
            p = c[k] if k >= 0 else np.nan
            lv = [x["pdH"], x["pdL"], x["asiaH"], x["asiaL"]] + ([x["ldnH"], x["ldnL"]] if w0 >= 300 else [])
            lv = np.array([v for v in lv if v == v])
            up, dn = lv[lv > p], lv[lv < p]
            lvh.append(up.min() if len(up) else np.nan)
            lvl.append(dn.max() if len(dn) else np.nan)
        lvh, lvl = np.array(lvh), np.array(lvl)
        b = lambda mins: max(1, mins // res)
        for liq, em, sm, (tm, rr) in itertools.product((1, 2, 0), (0, 1, 2, 3, 4), (0, 1),
                                                       ((0, 2.0), (0, 3.0), (1, 0.0), (2, 0.0))):
            pnl, rm, dd, _ = engine(o, h, l, c, scan0, win0, win1, xe, lvh, lvl, liq, b(15), b(30), b(30), em, sm, tm, rr,
                                 2, 3 if res == 1 else 2, COST)
            if len(pnl) < 40:
                continue
            y = dates[dd]
            rows.append(dict(familia="motor", res=f"{res}m", ventana=wn, liquidez={1: "externa", 2: "interna", 0: "ninguna"}[liq],
                             entrada=["fvg", "ce", "ote", "unicorn", "mercado"][em], stop=["extremo", "vela FVG"][sm],
                             objetivo={0: f"{rr:g}R", 1: "liquidez", 2: "cierre"}[tm], **stats(pnl, rm, y)))
    return rows, days, df


# ───────────────────────── familias simples ─────────────────────────

def simple_families(days, df):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rows = []

    def add(name, params, tr):
        if len(tr) < 40:
            return
        t = np.array([p for _, p in tr])
        y = np.array([d.year for d, _ in tr])
        rows.append(dict(familia=name, ventana=params, **stats(t, np.full(len(t), np.nan), y)))

    def hold(x, k, side, stop=None):
        e = c[k]
        for q in range(k + 1, x["rth1"] + 1):
            if stop is not None and ((side == 1 and l[q] <= stop) or (side == -1 and h[q] >= stop)):
                return side * ((min(stop, o[q]) if side == 1 else max(stop, o[q])) - e) - COST
        return side * (c[x["rth1"]] - e) - COST

    for T, mode in itertools.product((510, 570, 600, 630), ("descuento→largo", "seguir")):
        tr = []
        for x in days:
            k = at(x, T)
            mo = o[x["mid"]]
            side = 1 if c[k] < mo else -1
            if mode == "seguir":
                side = -side
            tr.append((x["d"], hold(x, k, side)))
        add("judas / apertura 00:00", f"{T // 60}:{T % 60:02d} {mode}", tr)
    for T in (570, 600, 630, 660):
        tr = []
        for x in days:
            k = at(x, T)
            mo = o[x["mid"]]
            seg = slice(x["mid"], k + 1)
            lo, hi = l[seg].min(), h[seg].max()
            if lo < mo < c[k] and (c[k] - lo) > 0 and hi - c[k] > 0:
                tr.append((x["d"], hold(x, k, 1, lo)))
            elif hi > mo > c[k]:
                tr.append((x["d"], hold(x, k, -1, hi)))
        add("PO3 / AMD", f"{T // 60}:{T % 60:02d}", tr)
    for mx, tgt, ex in itertools.product((0.5, 1.0, 3.0), ("ce", "cierre_ayer"), ("11:00", "16:00")):
        tr = []
        for x in days:
            k = x["rth0"]
            gap = o[k] - x["pC"]
            atr = x["dayH"] - x["dayL"]
            if gap == 0 or abs(gap) > mx * 0.01 * o[k]:
                continue
            side = -int(np.sign(gap))
            e = o[k]
            T = x["pC"] + gap / 2 if tgt == "ce" else x["pC"]
            stop = e + np.sign(gap) * abs(gap)
            k_end = at(x, 660) if ex == "11:00" else x["rth1"]
            res = side * (c[k_end] - e)
            for q in range(k, k_end + 1):
                if (side == 1 and l[q] <= stop) or (side == -1 and h[q] >= stop):
                    res = -abs(gap); break
                if (side == 1 and h[q] >= T) or (side == -1 and l[q] <= T):
                    res = abs(T - e); break
            tr.append((x["d"], res - COST))
        add("opening range gap (llenar)", f"hueco<{mx}% obj={tgt} salida {ex}", tr)
    return rows


# ───────────────────────── evaluación ─────────────────────────

def stats(pnl, rm, y):
    u = pnl * USD
    out = {}
    for name, sel, yrs in (("dev", y < SPLIT, 5), ("val", y >= SPLIT, 3.75)):
        v = u[sel]
        g, ls = v[v > 0].sum(), -v[v < 0].sum()
        eq = np.cumsum(v)
        out |= {f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs), f"{name}_pf": round(g / ls, 2) if ls else np.inf}
        if name == "val":
            out |= dict(val_dd=round((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0,
                        val_win=round((v > 0).mean(), 2) if len(v) else 0)
    by = pd.Series(u).groupby(y).sum()
    out["años"] = f"{(by > 0).sum()}/{len(by)}"
    out["by_year"] = by.round().astype(int).to_dict()
    return out


def report(r, title):
    both = lambda g: f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}"
    summ = lambda g: pd.Series({"n": len(g), "% gana ambos": both(g), "med dev": int(g.dev_usd.median()), "med val": int(g.val_usd.median())})
    print(f"\n══════════ {title}: {len(r)} variantes · ganan en ambos periodos: {both(r)} ══════════")
    m = r[r.familia == "motor"]
    if len(m):
        for col in ("res", "ventana", "liquidez", "entrada", "stop", "objetivo"):
            print(m.groupby(col).apply(summ, include_groups=False).to_string(), "\n")
    s = r[r.familia != "motor"]
    if len(s):
        print(s.groupby("familia").apply(summ, include_groups=False).to_string(), "\n")
    cols = [k for k in r.columns if k not in ("by_year",)]
    print("Mejor ELEGIDA con 2018-2022 en cada familia/ventana:")
    key = r.familia + " · " + r.ventana.astype(str).where(r.familia == "motor", "")
    print(r.loc[r.groupby(key).dev_usd.idxmax(), cols].to_string(index=False))
    print("\nLas 15 con el peor periodo más alto:")
    r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
    print(r.head(15)[cols].to_string(index=False))


def main():
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    out = {}
    for sym, resl in (("NQ", (1, 5)), ("ES", (5,))):
        rows = []
        for res in resl:
            rr, days, df = run_engine(sym, res)
            rows += rr
            if res == 5:
                rows += simple_families(days, df)
            print(f"{sym} {res}m listo", flush=True)
        r = pd.DataFrame(rows)
        r.to_pickle(f".lab_cache/ict_{sym}.pkl")
        out[sym] = r
        report(r, sym)


if __name__ == "__main__":
    main()
