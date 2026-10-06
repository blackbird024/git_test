"""Estrategias para la sesión de Londres en NQ / MNQ: búsqueda amplia con validación fuera de muestra.

Datos: velas de 5 min de NQ (Databento) 2018 - oct 2026, 24 h. Las horas de Londres se calculan en hora de
Londres (Europe/London), así que las semanas en que Europa y EE. UU. cambian de hora en fechas distintas
quedan bien. Se ELIGE con 2018-2022 y se JUZGA con 2023-2026; se mira qué fracción de cada rejilla gana en
ambos periodos y se repite en ES como control. Coste 1 punto; resultados por 1 MNQ (2 $/punto).

Horas (Londres): Asia 00:00-06:00 · apertura de Londres 08:00 · "killzone" 07:00-10:00 · NY abre 14:30.
Salidas posibles: 10:00, 12:00 o 14:25 (justo antes de la apertura de NY).

Familias:
  asia_brk   ruptura del rango de Asia (orden STOP en su máximo/mínimo), stop en el otro lado o en el medio
  asia_fade  barrida del rango de Asia: una vela de 5/15 min supera el máximo (mínimo) y CIERRA dentro → contra
             ella; stop en el extremo de la barrida; objetivo el medio o el otro lado de Asia
  ldn_orb    ruptura del rango de los primeros N min de Londres (desde las 08:00)
  ldn_vela   dirección de la primera vela de 5 min de Londres; stop a una fracción del ATR diario (como la ORB
             de 5 min de NY)
  asia_dir   la dirección de Asia (18:00 NY → 07:00 Londres) decide la operación: seguirla o ir contra ella
  tod        estar comprado en una franja fija (referencia: deriva alcista)

Uso:
    python london_research.py
"""

import itertools

import numpy as np
import pandas as pd

from crt_backtest import load_5m

COST = 1.0
USD = 2.0
SPLIT = 2023


def build(sym):
    df = load_5m(sym)
    tn = df.index
    tl = tn.tz_convert("Europe/London")
    gdate = (tn + pd.Timedelta(hours=6)).normalize().date
    lm = (tl.hour * 60 + tl.minute).to_numpy()
    lm = np.where(np.array(tl.date) < np.array(gdate), lm - 1440, lm)
    nm = (tn.hour * 60 + tn.minute).to_numpy()
    nm = np.where(nm >= 1080, nm - 1440, nm)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    days = []
    for d, idx in pd.Series(np.arange(len(df))).groupby(gdate).indices.items():
        idx = np.asarray(idx)
        L, N = lm[idx], nm[idx]
        keep = N < 600                                # hasta las 10:00 NY
        idx, L, N = idx[keep], L[keep], N[keep]
        if len(idx) < 150 or not ((L == 0).any() and (L == 480).any() and (N == 565).any()):
            continue
        days.append(dict(d=pd.Timestamp(d), o=o[idx], h=h[idx], l=l[idx], c=c[idx], lm=L, nm=N))
    rng = np.array([x["h"].max() - x["l"].min() for x in days])
    atr = pd.Series(rng).rolling(14).mean().shift(1).to_numpy()
    for x, a in zip(days, atr):
        x["atr"] = a
    return [x for x in days if np.isfinite(x["atr"])]


def exit_idx(x, ex):
    if ex == "14:25":
        return int(np.flatnonzero(x["nm"] == 565)[0])
    m = {"10:00": 595, "12:00": 715}[ex]
    j = np.flatnonzero(x["lm"] <= m)
    return int(j[-1])


def trade(x, k, side, e, stop, tgt, ke):
    """Entrada en la vela k al precio e; stop/objetivo revisados desde la vela k+1; cierre en la vela ke."""
    h, l, c, o = x["h"], x["l"], x["c"], x["o"]
    for q in range(k + 1, ke + 1):
        if (side == 1 and l[q] <= stop) or (side == -1 and h[q] >= stop):
            px = min(stop, o[q]) if side == 1 else max(stop, o[q])
            return side * (px - e) - COST
        if tgt is not None and ((side == 1 and h[q] >= tgt) or (side == -1 and l[q] <= tgt)):
            return side * (tgt - e) - COST
    return side * (c[ke] - e) - COST


def asia(x):
    s = (x["lm"] >= 0) & (x["lm"] < 360)
    return x["h"][s].max(), x["l"][s].min()


def asia_brk(days, start=420, last=600, stop="lado", rr=None, ex="12:00"):
    out = []
    for x in days:
        H, L = asia(x)
        ke = exit_idx(x, ex)
        for k in np.flatnonzero((x["lm"] >= start) & (x["lm"] < last)):
            if k >= ke:
                break
            up, dn = x["h"][k] > H, x["l"][k] < L
            if not (up or dn):
                continue
            side = 1 if up else -1
            e = H if up else L
            e = max(e, x["o"][k]) if up else min(e, x["o"][k])
            sl = (L if up else H) if stop == "lado" else (H + L) / 2
            risk = abs(e - sl)
            out.append((x["d"], trade(x, k, side, e, sl, e + side * rr * risk if rr else None, ke)))
            break
    return out


def asia_fade(days, tf=5, start=420, last=600, tgt="medio", ex="12:00", buf=0.0):
    out = []
    step = tf // 5
    for x in days:
        H, L = asia(x)
        ke = exit_idx(x, ex)
        ks = np.flatnonzero((x["lm"] >= start) & (x["lm"] < last))
        if len(ks) == 0:
            continue
        hi_run, lo_run = -np.inf, np.inf
        for a in range(ks[0], min(ks[-1] + 1, ke), step):
            b = min(a + step - 1, ke - 1)
            hh, ll, cc = x["h"][a:b + 1].max(), x["l"][a:b + 1].min(), x["c"][b]
            hi_run, lo_run = max(hi_run, hh), min(lo_run, ll)
            side = 0
            if hh > H and cc < H:
                side = -1
            elif ll < L and cc > L:
                side = 1
            if side == 0:
                continue
            e = cc
            sl = (hi_run + buf) if side == -1 else (lo_run - buf)
            T = (H + L) / 2 if tgt == "medio" else ((L if side == -1 else H) if tgt == "otro" else None)
            if T is not None and side * (T - e) <= 0:
                break
            out.append((x["d"], trade(x, b, side, e, sl, T, ke)))
            break
    return out


def ldn_orb(days, n=3, stop="lado", rr=None, last=600, ex="12:00"):
    out = []
    for x in days:
        k0 = int(np.flatnonzero(x["lm"] == 480)[0])
        if k0 + n >= len(x["o"]):
            continue
        H, L = x["h"][k0:k0 + n].max(), x["l"][k0:k0 + n].min()
        ke = exit_idx(x, ex)
        for k in range(k0 + n, ke):
            if x["lm"][k] >= last:
                break
            up, dn = x["h"][k] > H, x["l"][k] < L
            if not (up or dn):
                continue
            side = 1 if up else -1
            e = H if up else L
            e = max(e, x["o"][k]) if up else min(e, x["o"][k])
            sl = (L if up else H) if stop == "lado" else (H + L) / 2
            risk = abs(e - sl)
            out.append((x["d"], trade(x, k, side, e, sl, e + side * rr * risk if rr else None, ke)))
            break
    return out


def ldn_vela(days, frac=0.1, ex="12:00", only=0):
    out = []
    for x in days:
        k0 = int(np.flatnonzero(x["lm"] == 480)[0])
        side = int(np.sign(x["c"][k0] - x["o"][k0]))
        if side == 0 or (only and side != only):
            continue
        e = x["o"][k0 + 1]
        out.append((x["d"], trade(x, k0, side, e, e - side * frac * x["atr"], None, exit_idx(x, ex))))
    return out


def asia_dir(days, follow=True, ex="12:00", entry=480):
    out = []
    for x in days:
        k = int(np.flatnonzero(x["lm"] <= entry)[-1])
        side = int(np.sign(x["c"][k] - x["o"][0])) * (1 if follow else -1)
        if side == 0:
            continue
        e = x["c"][k]
        out.append((x["d"], trade(x, k, side, e, -np.inf if side == 1 else np.inf, None, exit_idx(x, ex))))
    return out


def tod(days, entry=480, ex="14:25"):
    out = []
    for x in days:
        k = int(np.flatnonzero(x["lm"] <= entry)[-1])
        out.append((x["d"], x["c"][exit_idx(x, ex)] - x["c"][k] - COST))
    return out


EXITS = ("10:00", "12:00", "14:25")
GRID = {
    "asia_brk": [dict(f=asia_brk, start=s, stop=st, rr=r, ex=e) for s, st, r, e in
                 itertools.product((420, 480), ("lado", "medio"), (None, 1, 2), EXITS)],
    "asia_fade": [dict(f=asia_fade, tf=tf, start=s, tgt=t, ex=e) for tf, s, t, e in
                  itertools.product((5, 15), (420, 480), ("medio", "otro", None), EXITS)],
    "ldn_orb": [dict(f=ldn_orb, n=n, stop=st, rr=r, ex=e) for n, st, r, e in
                itertools.product((1, 3, 6, 12), ("lado", "medio"), (None, 2), EXITS)],
    "ldn_vela": [dict(f=ldn_vela, frac=fr, ex=e, only=o) for fr, e, o in itertools.product((0.05, 0.1, 0.2), EXITS, (0, 1))],
    "asia_dir": [dict(f=asia_dir, follow=fo, ex=e, entry=en) for fo, e, en in itertools.product((True, False), EXITS, (420, 480))],
    "tod": [dict(f=tod, entry=en, ex=e) for en, e in itertools.product((420, 480), EXITS)],
}


def evaluate(tr):
    t = pd.DataFrame(tr, columns=["d", "pts"])
    if len(t) < 50:
        return None
    y = t.d.dt.year
    u = t.pts * USD
    r = {}
    for name, sel, yrs in (("dev", y < SPLIT, 5), ("val", y >= SPLIT, 3.75)):
        v = u[sel]
        g, ls = v[v > 0].sum(), -v[v < 0].sum()
        eq = v.cumsum()
        r |= {f"{name}_ops": round(len(v) / yrs), f"{name}_usd": round(v.sum() / yrs), f"{name}_pf": round(g / ls, 2) if ls else np.inf}
        if name == "val":
            r |= dict(val_dd=round((eq.cummax() - eq).max()), val_win=round((v > 0).mean(), 2))
    by = u.groupby(y).sum()
    r["años"] = f"{(by > 0).sum()}/{len(by)}"
    r["by_year"] = by.round().astype(int).to_dict()
    return r


def run(sym):
    days = build(sym)
    rows = []
    for fam, grid in GRID.items():
        for p in grid:
            q = {k: v for k, v in p.items() if k != "f"}
            r = evaluate(p["f"](days, **q))
            if r:
                rows.append(dict(fam=fam, params=", ".join(f"{k}={v}" for k, v in q.items()), **r))
    return pd.DataFrame(rows), len(days)


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    for sym in ("NQ", "ES"):
        r, n = run(sym)
        r.to_pickle(f".lab_cache/london_{sym}.pkl")
        print(f"\n══════════ {sym} ({n} días): $/año por 1 MNQ · dev 2018-2022 · val 2023-2026 ══════════")
        print(r.groupby("fam").apply(lambda g: pd.Series({
            "variantes": len(g), "% gana ambos": f"{((g.dev_usd > 0) & (g.val_usd > 0)).mean():.0%}",
            "mediana dev": int(g.dev_usd.median()), "mediana val": int(g.val_usd.median())}), include_groups=False).to_string())
        cols = [c for c in r.columns if c != "by_year"]
        print("\nMejor de cada familia ELEGIDA con 2018-2022:")
        print(r.loc[r.groupby("fam").dev_usd.idxmax(), cols].to_string(index=False))
        print("\nLas 12 con el peor periodo más alto:")
        r = r.assign(minimo=r[["dev_usd", "val_usd"]].min(axis=1)).sort_values("minimo", ascending=False)
        print(r.head(12)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
